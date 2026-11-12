"use strict";
const content=document.getElementById("content"),nav=document.getElementById("navigation");
let csrf="",view="Dashboard",epoch=0,dirty=new Set(),contactsOffset=0,contactSearch="",settingsCache=null,loggedIn=false;
const pendingWrites=new Set();
const offsets={Companies:0,Review:0,Queue:0,Tracking:0};
let operationId=null,reviewFocus=null;
const pages=["Dashboard","Contacts","Companies","Review","Queue","Tracking","Targets","Settings","Jobs"];
function el(tag,attrs={},...children){
    const node=document.createElement(tag);
    for(const [key,value] of Object.entries(attrs)){
        if(value===undefined||value===null)continue;
        if(key.startsWith("on"))node.addEventListener(key.slice(2),value);
        else if(key==="class")node.className=value;
        else if(["value","checked","disabled","hidden","type"].includes(key))node[key]=value;
        else node.setAttribute(key,String(value));
    }
    for(const child of children.flat(Infinity))if(child!==null&&child!==undefined)node.append(child instanceof Node?child:document.createTextNode(String(child)));
    return node;
}
function toast(message,error=false){const n=el("div",{class:"toast"+(error?" error":"")},message);document.getElementById("toasts").append(n);setTimeout(()=>n.remove(),6000);}
async function api(path,method="GET",data=null,requestKey=null){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
    const options={method,headers:{},signal:controller.signal};
    if(method!=="GET"){options.headers["X-CSRF-Token"]=csrf;options.headers["Idempotency-Key"]=requestKey||crypto.randomUUID();}
    if(data instanceof FormData)options.body=data;
    else if(data!==null){options.headers["Content-Type"]="application/json";options.body=JSON.stringify(data);}
    const task=(async()=>{
        const response=await fetch(path,options);
        let result;try{result=await response.json();}catch{throw new Error("Server returned an unreadable response. Check the connection.");}
        if(!response.ok){if(response.status===401)await loginScreen();const error=new Error(result.error||"Request failed");error.status=response.status;throw error;}
        return result;
    })();
    if(method!=="GET")pendingWrites.add(task);
    try{return await task;}catch(error){if(!error.status)throw new Error(method==="GET"?"Request timed out or connection failed. Retry when the server is reachable.":"Request outcome unknown. Check Jobs before retrying; your input has been preserved.");throw error;}finally{clearTimeout(timer);pendingWrites.delete(task);}
}
function button(label,fn,kind="",isDisabled=()=>false){
    const b=el("button",{type:"button",class:kind},label);
    b.addEventListener("click",async()=>{
        if(b.disabled)return;b.disabled=true;b.setAttribute("aria-busy","true");
        try{await fn(b);}catch(error){toast(error.message,true);}
        finally{b.disabled=isDisabled();b.removeAttribute("aria-busy");}
    });return b;
}
function field(label,input){const id=input.id||crypto.randomUUID();input.id=id;return el("div",{class:"field"},el("label",{for:id},label),input);}
function input(value="",type="text"){return el("input",{type,value:value||""});}
function title(text,...actions){return el("header",{},el("h2",{},text),el("div",{class:"actions"},actions));}
function table(headers,rows){return el("div",{class:"table-scroll"},el("table",{},el("thead",{},el("tr",{},headers.map(h=>el("th",{scope:"col"},h)))),el("tbody",{},rows)));}
function cell(value,wrap=false){return el("td",{class:wrap?"wrap":""},value);}
function option(value,label,selected=false){const o=el("option",{value},label);o.selected=selected;return o;}
function select(items,value){return el("select",{},items.map(([v,label])=>option(v,label,String(v)===String(value))));}
function card(heading,...children){return el("section",{class:"card"},el("h3",{},heading),children);}
function safeLink(url,label){try{if(new URL(url).protocol!=="https:")return el("span",{},label);return el("a",{href:url,target:"_blank",rel:"noopener noreferrer"},label);}catch{return el("span",{},label);}}
function modal(heading,form){
    const returnFocus=document.activeElement;
    const dialog=el("dialog",{"aria-label":heading},el("h2",{},heading),form);
    dialog.append(button("Cancel",()=>dialog.close()));
    dialog.addEventListener("close",()=>{dialog.remove();returnFocus?.focus();});
    document.body.append(dialog);dialog.showModal();return dialog;
}
async function queued(path,data={}){
    const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(path+JSON.stringify(data))))).map(n=>n.toString(16).padStart(2,'0')).join('');
    const storageKey='outreach-intent:'+digest;
    const key=localStorage.getItem(storageKey)||crypto.randomUUID();localStorage.setItem(storageKey,key);
    let job;
    try{job=await api(path,'POST',data,key);}
    catch(error){try{job=await api('/api/jobs/by-key/'+key);}catch{throw error;}}
    localStorage.removeItem(storageKey);
    operationId=job.id;
    toast("Operation queued. See Jobs for progress and results.");
    document.getElementById("operation-status").textContent="Job #"+job.id+" is "+job.status+". A worker processes queued operations.";
    return job;
}
async function reviewBatch(){
    const [plan,setup]=await Promise.all([api('/api/send-plan'),api('/api/settings')]);
    const data={members:plan.members.map(r=>({id:r.id,revision:r.revision})),batch_sender:plan.sender};
    const outcomes=new Map(plan.preflight.map(r=>[r.id,r]));
    const body=el('div',{},el('p',{},'Sender: '+(plan.sender||'Not configured')+' · '+plan.members.length+' messages | Projected eligible: '+plan.projected_eligible+'  · Daily remaining: '+setup.configuration.daily_remaining),
        el('p',{},'Only these revisions are included. Changed messages are skipped. Delivery rechecks quotas, suppressions and the send window.'),
        table(['Recipient','Company','Subject','Revision','Preflight'],plan.members.map(r=>el('tr',{},cell(r.contact_email),cell(r.company_name),cell(r.subject,true),cell(r.revision),cell(outcomes.get(r.id)?.reason||outcomes.get(r.id)?.status||'Unavailable',true)))));
    const dialog=modal('Review send batch',body);
    body.append(button('Preview this batch',()=>queued('/api/send',{...data,dry_run:true})),button('Send this batch',async()=>{await queued('/api/send',data);dialog.close();},'primary'));
}
async function navigate(next){
    await Promise.allSettled([...pendingWrites]);
    if(dirty.size&&!confirm("Leave without saving your edits?"))return;
    dirty.clear();view=next;
    nav.querySelectorAll("button").forEach(b=>b.setAttribute("aria-current",b.textContent===view?"page":"false"));
    await render();
}
async function render(){
    const serial=++epoch;content.setAttribute("aria-busy","true");
    try{const node=await loaders[view]();if(serial===epoch)content.replaceChildren(node);}
    catch(error){if(serial===epoch&&loggedIn)content.replaceChildren(el("div",{class:"error",role:"alert"},error.message),button("Retry",render));}
    finally{if(serial===epoch)content.setAttribute("aria-busy","false");}
}
async function dashboard(){
    const [data,setup]=await Promise.all([api("/api/stats"),api("/api/settings")]);settingsCache=setup;
    const root=el("div",{},title("Dashboard",button("Refresh",render),button("Preview send batch",()=>queued("/api/send",{dry_run:true})),button("Send approved batch",reviewBatch,"primary"),button("Check replies",()=>queued("/api/check_replies"))));
    const missing=Object.entries(setup.readiness).filter(([,ready])=>!ready).map(([key])=>key);
    if(missing.length)root.append(el("p",{class:"notice"},"Setup needed: "+missing.join(", ")+". Open Settings before drafting or sending."));
    root.append(el("p",{class:"notice"},"Daily remaining capacity: "+setup.configuration.daily_remaining+" of "+setup.configuration.daily_cap+". Outstanding uncertain attempts consume capacity."));
    root.append(el("div",{class:"grid"},["pending_review","approved","sent","replied"].map(key=>card(key.replaceAll("_"," "),el("div",{class:"metric"},data.summary[key]||0)))));
    root.append(card("Resume performance",el("p",{class:"muted"},"Rates count sent messages, including follow-ups."),table(["Resume","Sent","Replies","Interviews","Offers","Reply rate"],data.stats.by_variant.map(v=>el("tr",{},[v.name,v.sent,v.replied,v.interviews,v.offers,v.reply_rate+"%"].map(value=>cell(value)))))));
    return root;
}
async function contactsView(){
    const [people,companies,setup,targets]=await Promise.all([api("/api/contacts?limit=100&offset="+contactsOffset+"&search="+encodeURIComponent(contactSearch)),api("/api/companies"),api("/api/settings"),api("/api/opportunities")]);
    const draftResume=select([["auto","Automatic match"],["none","No resume"],...setup.resumes.map(r=>[r.id,r.name])],"auto");
    const target=select([[0,"Company context (no selected role)"],...targets.map(t=>[t.id,(companies.find(c=>c.id===t.company_id)?.name||"Company #"+t.company_id)+" / "+t.role])],0);
    function chosenTarget(person){const selected=targets.find(t=>t.id===Number(target.value));if(selected&&selected.company_id!==person.company_id)throw new Error("Choose a role at this contact's company.");return selected?.id||null;}
    function draftFor(person){
        const data={company_id:person.company_id,contact_id:person.id,opportunity_id:chosenTarget(person)};
        if(draftResume.value!=="auto")data.resume_variant_id=draftResume.value==="none"?null:Number(draftResume.value);
        return queued("/api/compose",data);
    }
    const search=input(contactSearch);search.setAttribute("aria-label","Search contacts");
    const file=el("input",{type:"file",accept:".csv","aria-label":"Import contacts CSV"});
    file.addEventListener("change",async()=>{if(!file.files.length)return;const form=new FormData();form.append("file",file.files[0]);try{const r=await api("/api/contacts/import","POST",form);toast(r.contacts_created+" contacts added; "+r.duplicates_skipped+" duplicates skipped.");if(r.errors.length)toast(r.errors.map(e=>"Row "+e.row+": "+e.error).join("; "),true);await render();}catch(e){toast(e.message,true);}finally{file.value="";}});
    const root=el("div",{},title("Contacts",button("Add contact",()=>contactForm(companies)),button("Search",async()=>{contactSearch=search.value;contactsOffset=0;await render();})),field("Search name, company or email",search),field("Import CSV",file));
    root.append(field("Role for new drafts",target),field("Resume for new drafts",draftResume));
    root.append(table(["Company","Name","Email","Actions"],people.map(p=>el("tr",{},cell(p.company_name,true),cell(p.name||"—",true),cell(p.email),cell(el("div",{class:"actions"},button("Draft",()=>draftFor(p)),button("Write manually",()=>manualDraftForm(p,setup,chosenTarget(p))),button("Edit",()=>contactForm(companies,p)),button("Do not contact",()=>suppressAddress(p.email)),button("Check DNS",async()=>{const result=await api("/api/contacts/"+p.id+"/validate","POST",{});toast((result.warning||"Domain accepts mail in DNS")+". "+result.note,!!result.warning);})))))));
    if(!people.length)root.append(el("p",{},"No contacts found. Add a company first, or import the sample CSV."));
    root.append(el("div",{class:"actions"},button("Previous",async()=>{contactsOffset=Math.max(0,contactsOffset-100);await render();}),button("Next",async()=>{if(people.length===100){contactsOffset+=100;await render();}})));
    return root;
}
function manualDraftForm(person,setup,opportunityId=null){
    const subject=input(),body=el('textarea',{rows:8}),variant=select([['none','No resume'],...setup.resumes.map(r=>[r.id,r.name])],'none');
    const form=el('div',{},field('Subject',subject),field('Pitch (greeting and signature are added)',body),field('Resume',variant));
    const dialog=modal('Write manually',form);
    form.append(button('Create draft',async()=>{await api('/api/drafts/manual','POST',{company_id:person.company_id,contact_id:person.id,opportunity_id:opportunityId,subject:subject.value,body:body.value,resume_variant_id:variant.value==='none'?null:Number(variant.value)});dialog.close();await navigate('Review');},'primary'));
}
function followupForm(original,setup){
    const variant=select([['original','Use original resume'],['none','No resume'],...setup.resumes.map(r=>[r.id,r.name])],'original');
    const form=el('div',{},field('Follow-up resume',variant));const dialog=modal('Draft follow-up',form);
    form.append(button('Generate follow-up',async()=>{const data={};if(variant.value!=='original')data.resume_variant_id=variant.value==='none'?null:Number(variant.value);await queued('/api/tracking/'+original.id+'/followup',data);dialog.close();}));
}
async function contactForm(companies,person=null){
    if(person&&!companies.some(c=>c.id===person.company_id))companies=[await api("/api/companies/"+person.company_id),...companies];
    if(!companies.length){toast("Add a company first in Companies.",true);return;}
    const company=select(companies.map(c=>[c.id,c.name]),person?.company_id||companies[0].id),name=input(person?.name),email=input(person?.email,"email"),role=input(person?.title),source=input(person?.source);
    company.disabled=!!person;
    const body=el("div",{},field("Company",company),field("Name",name),field("Email",email),field("Role / title",role),field("Source",source));
    const search=input(),status=el('p',{},'Selected company is preserved while browsing matches.');let companyOffset=0,searchSerial=0,pageSize=companies.length;
    async function loadCompanies(){const serial=++searchSerial;const found=await api('/api/companies?limit=100&offset='+companyOffset+'&search='+encodeURIComponent(search.value));if(serial!==searchSerial)return;const selected=company.value,label=company.selectedOptions[0]?.textContent;company.replaceChildren(...found.map(c=>option(c.id,c.name,String(c.id)===selected)));if(selected&&!found.some(c=>String(c.id)===selected))company.prepend(option(selected,label||'Selected company',true));pageSize=found.length;status.textContent='Company matches page '+(companyOffset/100+1)+'; '+found.length+' matches shown. Selected company preserved.';}
    body.prepend(field('Find company',search),el('div',{class:'actions'},button('Find companies',async()=>{companyOffset=0;await loadCompanies();}),button('Previous company matches',async()=>{companyOffset=Math.max(0,companyOffset-100);await loadCompanies();}),button('Next company matches',async()=>{if(pageSize===100){companyOffset+=100;await loadCompanies();}})),status);
    const dialog=modal(person?"Edit contact":"Add contact",body);
    body.append(button("Save",async()=>{const values={name:name.value,email:email.value,title:role.value,source:source.value};if(!person)values.company_id=Number(company.value);await api(person?"/api/contacts/"+person.id:"/api/contacts",person?"PATCH":"POST",values);dialog.close();await render();},"primary"));
    if(person)body.append(button("Archive",async()=>{await api("/api/contacts/"+person.id,"PATCH",{archived:true});dialog.close();await render();},"danger"));
}
async function companiesView(){
    const companies=await api("/api/companies?limit=100&offset="+offsets.Companies);
    const root=el("div",{},title("Companies",button("Add company",()=>companyForm())),table(["Company","Domain","Contacts","Actions"],companies.map(c=>el("tr",{},cell(c.name,true),cell(c.domain||"—"),cell(c.contact_count),cell(el("div",{class:"actions"},button("Edit",()=>companyForm(c)),button("Add contact",()=>contactForm([c]))))))));
    paginate(root,"Companies",companies);return root;
}
function companyForm(company=null){
    const fields={name:input(company?.name),domain:input(company?.domain),job_url:input(company?.job_url,"url"),job_text:el("textarea",{value:company?.job_text||""}),notes:el("textarea",{value:company?.notes||""})};
    const body=el("div",{},Object.entries(fields).map(([key,node])=>field(key.replaceAll("_"," "),node)));
    const dialog=modal(company?"Edit company":"Add company",body);
    body.append(button("Save",async()=>{const data=Object.fromEntries(Object.entries(fields).map(([key,node])=>[key,node.value]));await api(company?"/api/companies/"+company.id:"/api/companies",company?"PATCH":"POST",data);dialog.close();await render();},"primary"));
}
async function targetsView(){
    const [companies,targets,projects]=await Promise.all([api('/api/companies?limit=500'),api('/api/opportunities'),api('/api/projects')]);
    const root=el('div',{},title('Targets and project evidence',button('Add role brief',async()=>targetForm(companies,await api('/api/projects'))),button('Edit project evidence',()=>projectsForm(projects))),el('p',{},'Record only facts you can support. Application status, relationships and results are owner supplied. Source links and AI notes require independent review.'),table(['Company','Role','Level','Application','Actions'],targets.map(t=>el('tr',{},cell(companies.find(c=>c.id===t.company_id)?.name||t.company_id),cell(t.role),cell(t.level||'Unknown'),cell(t.application_status||'Unknown'),cell(button('Edit role brief',()=>targetForm(companies,projects,t)))))));
    root.append(card('Your projects',projects.map(p=>el('p',{},p.name+': '+p.action+' / '+(p.result||'No measured result')))));
    return root;
}
function targetForm(companies,projects,target=null){
    if(!companies.length){toast('Add a company first.',true);return;}
    const company=select(companies.map(c=>[c.id,c.name]),target?.company_id||companies[0].id);company.disabled=!!target;
    const nodes={};
    for(const key of ['role','level','role_url','requisition','application_date','constraints','relationship','company_source','source_verified_date'])nodes[key]=input(target?.[key]||'',key.endsWith('date')?'date':key.includes('url')||key==='company_source'?'url':'text');
    nodes.application_status=select([['unknown','Unknown'],['not_applied','Not applied'],['applied','Applied (owner confirmed)']],target?.application_status||'unknown');
    nodes.project_id=select([['','No selected project'],...projects.map(p=>[p.id,p.name])],target?.project_id||'');
    nodes.job_text=el('textarea',{rows:6,value:target?.job_text||''});
    const form=el('div',{},field('Company',company),Object.entries(nodes).map(([k,n])=>field(k.replaceAll('_',' '),n)));
    const dialog=modal(target?'Edit role brief':'Add role brief',form);
    form.append(button('Save role brief',async()=>{const data=Object.fromEntries(Object.entries(nodes).map(([k,n])=>[k,n.value]));if(!target)data.company_id=Number(company.value);await api(target?'/api/opportunities/'+target.id:'/api/opportunities',target?'PATCH':'POST',data);dialog.close();await render();},'primary'));
}
function projectsForm(projects){
    const entries=[0,1,2].map(i=>{const p=projects[i]||{};return {id:p.id,name:input(p.name),action:el('textarea',{value:p.action||''}),result:input(p.result),proof_url:input(p.proof_url,'url')};});
    const form=el('div',{},entries.map((e,i)=>card('Project '+(i+1),field('Project name '+(i+1),e.name),field('What you built or did '+(i+1),e.action),field('Actual result (optional) '+(i+1),e.result),field('Proof URL (optional) '+(i+1),e.proof_url))));
    const dialog=modal('Edit project evidence',form);
    form.append(button('Save projects',async()=>{const items=entries.filter(e=>e.name.value.trim()||e.action.value.trim()).map(e=>({...(e.id?{id:e.id}:{}),name:e.name.value,action:e.action.value,result:e.result.value,proof_url:e.proof_url.value}));await api('/api/projects','POST',{projects:items});await render();dialog.close();},'primary'));
}
async function reviewView(){
    const [drafts,setup]=await Promise.all([api(reviewFocus?"/api/review?email_id="+reviewFocus:"/api/review?limit=100&offset="+offsets.Review),api("/api/settings")]);
    const root=el("div",{},title("Review queue"));
    if(!drafts.length)root.append(el("p",{},"No drafts awaiting review."));
    for(let draft of drafts){
        let writing=false,editSerial=0,save,reject;
        const subject=input(draft.subject),hook=input(draft.hook),body=el("textarea",{value:draft.body||"",rows:8});
        const variant=select([[0,"No resume"],...(draft.resume_variant_id&&!setup.resumes.some(r=>r.id===draft.resume_variant_id)?[[draft.resume_variant_id,"Unavailable selected resume - choose a replacement or No resume"]]:[]),...setup.resumes.map(r=>[r.id,r.name])],draft.resume_variant_id||0);
        const warnings=el("p",{class:"warning"},draft.qc_warnings||"Review facts, recipient, content and resume before approving.");
        const status=el("p",{class:"muted"},"Revision "+draft.revision+" · Pending review · Sender: "+(setup.configuration.sender||"Configure Gmail before approving"));
        const approve=button("Approve saved revision",()=>writeReview(async()=>{await api("/api/review/"+draft.id,"POST",{action:"approve",revision:draft.revision});dirty.delete(draft.id);section.remove();toast("Approved. Available in Queue.");},true),"primary",()=>writing||dirty.has(draft.id)||(draft.opportunity_id&&!draft.evidence_verified_at));
        const section=card(draft.company_name+" · "+draft.contact_email,status,field("Subject",subject),field("Research hook",hook),field("Body",body),field("Resume choice",variant),warnings);
        function syncActions(){save.disabled=writing;reject.disabled=writing;approve.disabled=writing||dirty.has(draft.id)||!!(draft.opportunity_id&&!draft.evidence_verified_at);}
        async function writeReview(action,lockInputs=false){
            if(writing)return;
            writing=true;syncActions();
            if(lockInputs)for(const node of [subject,hook,body,variant])node.disabled=true;
            try{await action();}
            finally{writing=false;for(const node of [subject,hook,body,variant])node.disabled=false;syncActions();}
        }
        const mark=()=>{editSerial++;dirty.add(draft.id);approve.disabled=true;status.textContent="Unsaved edits — save before approving";};
        for(const node of [subject,hook,body,variant])node.addEventListener("input",mark);
        section.append(el("details",{},el("summary",{},"Research notes and sources"),el("p",{class:"warning"},"AI-written notes and URLs require independent verification."),el("pre",{},draft.research_notes||"No source evidence saved; verify company claims independently."),
            el("ul",{class:"sources"},[...new Set((draft.research_notes||"").match(/https:\/\/[^\s<>]+/g)||[])].map(url=>el("li",{},safeLink(url,url)))),
            el("pre",{},draft.grounding_json||"")));
        const evidence=draft.input_snapshot_json?JSON.parse(draft.input_snapshot_json):null;
        if(evidence){
            const proof=evidence.project,role=evidence.opportunity;
            section.append(card('Draft evidence',el('p',{},'Owner-supplied role: '+(role?.role||'No role selected')),el('p',{},'Owner-supplied proof: '+(proof?proof.name+' / '+proof.action+' / '+(proof.result||'No measured result supplied'):'Candidate facts in saved inputs')),proof?.proof_url?safeLink(proof.proof_url,'Open project proof'):null,role?.company_source?safeLink(role.company_source,'Company source (verify independently)'):null,el('p',{},'Owner-reported source verification date: '+(role?.source_verified_date||'None')+' | Draft acknowledgment: '+(draft.evidence_verified_at||'Not yet verified')),el('details',{},el('summary',{},'Saved generation inputs and model version'),el('pre',{},JSON.stringify(evidence,null,2))),button('I verified this saved revision',()=>writeReview(async()=>{if(dirty.has(draft.id))throw new Error('Save your edits before verifying.');const result=await api('/api/review/'+draft.id+'/verify-evidence','POST',{revision:draft.revision});draft=result.email;toast('Verification recorded for this revision.');},true))));
        }
        const asset=el("div",{});
        function showAsset(){
            const selected=setup.resumes.find(r=>r.id===Number(variant.value));
            asset.replaceChildren(el("p",{class:"muted"},"Delivery mode: "+setup.configuration.resume_mode));
            if(!selected)asset.append(el("p",{},Number(variant.value)?"Selected resume is unavailable. Choose a replacement or deliberately select No resume.":"No resume selected."));
            else if(setup.configuration.resume_mode==="link")asset.append(selected.resume_url?safeLink(selected.resume_url,"Open selected resume link"):el("p",{class:"warning"},"This variant needs an HTTPS link before approval."));
            else if(selected.file_path)asset.append(el("a",{href:"/api/resumes/"+selected.id+"/pdf",class:"button"},"Download selected PDF"));
            else asset.append(el("p",{class:"warning"},"This variant needs a PDF before approval."));
        }
        variant.addEventListener("change",showAsset);showAsset();section.append(asset);
        save=button("Save edits",()=>writeReview(async()=>{
            const savingSerial=editSerial;
            const result=await api("/api/review/"+draft.id,"POST",{action:"edit",revision:draft.revision,subject:subject.value,hook:hook.value,body:body.value,resume_variant_id:Number(variant.value)||null});
            draft=result.email;
            if(savingSerial===editSerial)dirty.delete(draft.id);
            warnings.textContent=draft.qc_warnings||"No deterministic warnings; verify all facts.";
            status.textContent=dirty.has(draft.id)?"Newer unsaved edits — save before approving":"Revision "+draft.revision+" · Saved, awaiting approval";
            toast(dirty.has(draft.id)?"Earlier edits saved. Save the newer edits before approving.":"Saved. Approval is still required.");
        }),"",()=>writing);
        reject=button("Reject",()=>writeReview(async()=>{await api("/api/review/"+draft.id,"POST",{action:"reject",revision:draft.revision});dirty.delete(draft.id);section.remove();toast("Draft rejected.");},true),"danger",()=>writing);
        section.append(el("div",{class:"actions"},save,approve,reject,button("Regenerate",async()=>{if(dirty.has(draft.id)){toast("Save your edits before regenerating.",true);return;}if(!confirm("Replace this draft with AI output? Manual edits will be replaced only if generation succeeds; review and approval will be required again."))return;await queued("/api/review/"+draft.id+"/regenerate",{revision:draft.revision,resume_variant_id:Number(variant.value)||null});})));
        section.append(button('Preview final email',async()=>{if(dirty.has(draft.id))throw new Error('Save edits before previewing the final email.');const preview=await api('/api/review/'+draft.id+'/preview');modal('Final email preview',el('div',{},el('p',{},'From: '+preview.sender),el('p',{},'To: '+preview.recipient),el('p',{},'Subject: '+preview.subject),el('pre',{},preview.body),el('p',{},'Attachments: '+(preview.attachments.join(', ')||'None'))));}));
        syncActions();
        root.append(section);
    }
    if(!reviewFocus)paginate(root,"Review",drafts);return root;
}
async function queueView(){
    const items=await api("/api/queue?limit=100&offset="+offsets.Queue);
    const root=el("div",{},title("Approved queue",button("Send approved batch",reviewBatch,"primary")),el("p",{},"Only the approved revision and attachment may send. Caps, suppression and send windows are checked again at delivery."),
        table(["Company","Recipient","Subject","Actions"],items.map(r=>el("tr",{},cell(r.company_name,true),cell(r.contact_email),cell(r.subject,true),cell(button("Return to review",async()=>{await api("/api/review/"+r.id,"POST",{action:"edit",revision:r.revision});await render();}))))));
    paginate(root,"Queue",items);return root;
}
async function suppressAddress(address){
    const reason=input('Requested no further contact');
    const body=el('div',{},el('p',{},address),field('Reason for suppression',reason));
    const dialog=modal('Do not contact',body);
    body.append(button('Suppress address',async()=>{await api('/api/suppressions','POST',{email:address,reason:reason.value});dialog.close();await render();toast('Address suppressed. Unsubmitted drafts canceled.');},'danger'));
}
async function trackingView(){
    const [tracked,due,attempts,setup]=await Promise.all([api("/api/tracking?limit=100&offset="+offsets.Tracking),api("/api/tracking/due"),api("/api/attempts"),api('/api/settings')]);
    const root=el("div",{},title("Tracking",button("Refresh",render),button("Check replies",()=>queued("/api/check_replies"))));
    const scan=setup.reply_scan.length?JSON.parse(setup.reply_scan[0].value):null;
    root.append(card('Reply scan coverage',el('p',{},scan?'Mailbox: '+scan.mailbox+' · Last check: '+(scan.checked_at||'Incomplete')+' · Remaining: '+(scan.remaining??'unknown')+' · Unreviewed reports: '+(scan.unreviewed_reports??0):'No reply scan yet.'),el('p',{},'Follow-ups require a current complete scan. Replies can still arrive after checking. Only the configured mailbox is scanned.'),button('Continue scan',()=>queued('/api/check_replies'))));
    for(const report of setup.skipped_reply_reports){const details=JSON.parse(report.value);root.append(card('Skipped delivery report',el('p',{},'Inspect message UID '+details.uid+' in '+details.mailbox+' and record its outcome before acknowledging it.'),button('I reviewed this report',async()=>{await api('/api/reply-reports/review','POST',{key:report.key});await render();})));}
    root.append(card("Due for follow-up",table(["Company","Recipient","Actions"],due.map(r=>el("tr",{},cell(r.company_name,true),cell(r.contact_email),cell(button("Draft follow-up",()=>followupForm(r,setup))))))));
    const statuses=["replied","ghosted","bounced","interview_scheduled","interview_completed","offer","no_offer"];
    root.append(table(["Company","Recipient","Status","Sent","Update"],tracked.map(r=>{
        const choice=select(statuses.map(s=>[s,s.replaceAll("_"," ")]),r.status);
        choice.setAttribute("aria-label","Outcome for email #"+r.id);
        const action=el("div",{class:"actions"},button("Do not contact",()=>suppressAddress(r.contact_email)));
        if(r.sent_at)action.append(choice,button("Apply outcome",async()=>{await api("/api/tracking/"+r.id+"/mark","POST",{status:choice.value});await render();}));
        if(["failed","canceled"].includes(r.status))action.append(button("Review retry",async()=>{await api("/api/emails/"+r.id+"/retry","POST",{});await render();toast("Returned to review. Approve again after resolving the failure.");}));
        return el("tr",{},cell(r.company_name,true),cell(r.contact_email),cell(r.status),cell(r.sent_at?new Date(r.sent_at).toLocaleString():"Not confirmed sent"),cell(action));
    })));
    for(const attempt of attempts.filter(a=>a.state==="uncertain")){
        root.append(card("Uncertain delivery #"+attempt.id,el("p",{class:"warning"},"Do not resend automatically. Check Sent Mail for Message-ID "+attempt.message_id+" and confirm what happened."),
            button("Confirm delivered",async()=>{if(confirm("Have you confirmed this exact Message-ID was sent?")){await api("/api/attempts/"+attempt.id+"/reconcile","POST",{accepted:true});await render();}}),
            button("Confirm not sent",async()=>{if(confirm("Have you confirmed this message was NOT submitted? A later retry requires new review.")){await api("/api/attempts/"+attempt.id+"/reconcile","POST",{accepted:false});await render();}})));
    }
    paginate(root,"Tracking",tracked);return root;
}
function resumeForm(resume,refresh){
    const name=input(resume.name),keywords=input(resume.keywords),url=input(resume.resume_url,'url'),file=el('input',{type:'file',accept:'.pdf'});
    const form=el('div',{},field('Variant name',name),field('Keywords',keywords),field('Resume URL',url),field('Replacement PDF (optional)',file));const dialog=modal('Edit resume variant',form);
    form.append(button('Save resume variant',async()=>{let id=resume.id;if(file.files.length){const data=new FormData();data.append('file',file.files[0]);data.append('name',name.value);data.append('keywords',keywords.value);data.append('resume_url',url.value);await api('/api/resumes/'+id+'/replace','POST',data);}else await api('/api/resumes/'+id,'PATCH',{name:name.value,keywords:keywords.value,resume_url:url.value});await refresh();dialog.close();toast('Resume updated. Affected drafts require review again.');},'primary'));
}
async function settingsView(){
    const setup=await api("/api/settings");settingsCache=setup;
    const readiness=el("p",{},Object.entries(setup.readiness).map(([key,ready])=>key+": "+(ready?"configured":"needed")).join(" · "));
    const root=el("div",{},title("Settings"),card("Readiness",readiness,el("p",{class:"muted"},"Provider connections have not been verified. Configuration presence alone does not establish account access."),
        el("p",{class:"muted"},"Model: "+setup.configuration.model+" · Timezone: "+setup.configuration.timezone+" · Resume mode: "+setup.configuration.resume_mode)));
    const fields={};for(const key of ["full_name","email","phone","linkedin_url","github_url","portfolio_url"])fields[key]=input(setup.profile?.[key],key.includes("url")?"url":key==="email"?"email":"text");
    const context=el("textarea",{value:setup.candidate_context,rows:6});
    let editSerial=0;
    for(const node of [...Object.values(fields),context])node.addEventListener("input",()=>{editSerial++;dirty.add("settings");});
    const resumeList=el("div",{}),suppressionList=el("div",{});
    let listSerial=0;
    function showLists(data){
        const resumeRows=data.resumes.map(r=>{const actions=el('div',{class:'actions'},button('Edit or replace',()=>resumeForm(r,refreshLists)),button('Archive resume',async()=>{await api('/api/resumes/'+r.id,'DELETE',{});await refreshLists();}));return el('tr',{},cell(r.name,true),cell(r.keywords,true),cell(r.resume_url?safeLink(r.resume_url,'Open resume link'):'PDF registered'),cell(actions));});
        resumeList.replaceChildren(table(['Name','Keywords','Link','Actions'],resumeRows));
        suppressionList.replaceChildren(table(["Address","Reason","Actions"],data.suppressions.map(r=>el("tr",{},cell(r.email),cell(r.reason,true),cell(button("Remove suppression",async()=>{await api("/api/suppressions","DELETE",{email:r.email});await refreshLists();}))))));
    }
    async function refreshLists(){const serial=++listSerial;const data=await api("/api/settings");if(serial===listSerial){settingsCache=data;showLists(data);}}
    showLists(setup);
    root.append(card("Profile and verified candidate facts",Object.entries(fields).map(([key,node])=>field(key.replaceAll("_"," "),node)),field("Candidate facts — include only truthful skills and achievements",context),
        button("Preview legacy context.txt",async()=>{if(context.value.trim()&&!confirm("Replace the visible facts with a preview of context.txt? Saved facts will change only when you save."))return;const data=await api("/api/settings/legacy-context");context.value=data.candidate_context;context.dispatchEvent(new Event("input"));context.focus();toast("Legacy facts loaded for review. Check them, then save profile and facts to import.");}),
        button("Save profile and facts",async()=>{
            const savingSerial=editSerial;
            const data={profile:Object.fromEntries(Object.entries(fields).map(([key,node])=>[key,node.value])),candidate_context:context.value};
            await api("/api/settings","POST",data);
            if(savingSerial===editSerial)dirty.delete("settings");
            setup.readiness.profile=true;setup.readiness.context=!!data.candidate_context.trim();
            readiness.textContent=Object.entries(setup.readiness).map(([key,ready])=>key+": "+(ready?"ready":"needed")).join(" · ");
            toast(dirty.has("settings")?"Profile and facts saved. Newer edits remain unsaved.":"Profile and facts saved.");
        },"primary")));
    const name=input(),keywords=input(),url=input("","url"),file=el("input",{type:"file",accept:".pdf"});
    root.append(card("Resume variants",el("p",{},"Upload PDFs you wrote, or register a public HTTPS link. Delivery uses the configured mode."),
        field("Resume name",name),field("Matching keywords, separated by commas",keywords),field("PDF",file),field("HTTPS resume link (optional for attachments)",url),
        button("Register resume",async()=>{
            let data;if(file.files.length){data=new FormData();data.append("file",file.files[0]);data.append("name",name.value);data.append("keywords",keywords.value);data.append("resume_url",url.value);}
            else data={name:name.value,keywords:keywords.value,resume_url:url.value};
            await api("/api/resumes","POST",data);toast("Resume registered.");await refreshLists();
        }),resumeList));
    const address=input("","email"),reason=input();
    root.append(card("Suppressions",field("Email to suppress",address),field("Reason",reason),button("Suppress address",async()=>{await api("/api/suppressions","POST",{email:address.value,reason:reason.value});await refreshLists();}),suppressionList));
    if(setup.duplicate_contacts.length)root.append(card("Duplicate contacts to review",
        el("p",{},"Keep the record you intend to use and archive redundant contacts after checking their history. Archiving preserves sent history and cancels unsubmitted drafts."),
        table(["Company","Address","Records","Review"],setup.duplicate_contacts.map(group=>el("tr",{},cell(group.company_name,true),cell(group.email),cell(group.contact_ids),cell(button("Review contacts",async()=>{contactSearch=group.email;contactsOffset=0;await navigate("Contacts");})))))));
    if(setup.worker.length)root.append(el("p",{class:"muted"},"Worker last seen: "+new Date(setup.worker[0].value).toLocaleString()));
    else root.append(el("p",{class:"warning"},"Worker has not started for this database."));
    if(setup.migration_reports.length)root.append(card("Legacy data needs review",el("pre",{},JSON.stringify(setup.migration_reports,null,2)),el("p",{},"Existing records were preserved. Resolve duplicate identities or mismatched relationships before reusing them.")));
    return root;
}
async function jobsView(){
    const [jobs,worker]=await Promise.all([api('/api/jobs'),api('/api/worker')]);
    const root=el('div',{},title('Jobs',button('Refresh',render)),card('Worker',el('p',{},worker.state+' | '+worker.stage),el('p',{},'Last seen: '+(worker.last_seen||'Never')+' | Last progress: '+(worker.last_progress||'None'))));
    for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(!key.startsWith('outreach-intent:'))continue;const value=localStorage.getItem(key);root.append(card('Request outcome unknown',el('p',{},'Check whether this operation was recorded before trying it again.'),button('Check request',async()=>{const found=await api('/api/jobs/by-key/'+value);localStorage.removeItem(key);operationId=found.id;await render();})));}
    for(const j of jobs){
        const box=card('#'+j.id+' / '+j.kind+' / '+j.status,j.error?el('p',{class:'error',role:'alert'},j.error):null);
        if(j.kind==='send'&&['pending','running'].includes(j.status))box.append(button(j.status==='pending'?'Cancel batch':'Stop remaining',async()=>{await api('/api/jobs/'+j.id+'/stop','POST',{});await render();}));
        if(j.result?.id)box.append(button('Open draft',async()=>{reviewFocus=j.result.id;await navigate('Review');}));
        if(j.result?.summary)box.append(table(['Message','Result','Reason','Action'],j.result.summary.map(r=>el('tr',{},cell('#'+r.id),cell(r.status),cell(r.reason||'',true),cell(['failed','canceled'].includes(r.status)?button('Return to review',async()=>{await api('/api/emails/'+r.id+'/retry','POST',{});await navigate('Review');}):r.status==='uncertain'?button('Resolve uncertain send',()=>navigate('Tracking')):null)))));
        if(j.kind==='replies'&&j.result){box.append(el('p',{},'Scanned '+j.result.scanned+' | Remaining '+j.result.remaining+' | Skipped '+j.result.skipped));if(!j.result.complete)box.append(button('Continue scan',()=>queued('/api/check_replies')));}
        box.append(el('details',{},el('summary',{},'Diagnostics'),el('pre',{},JSON.stringify(j.result||{},null,2))));root.append(box);
    }
    return root;
}
function paginate(root,name,items){
    const previous=button("Previous",async()=>{if(dirty.size&&!confirm("Leave without saving your draft edits?"))return;dirty.clear();offsets[name]=Math.max(0,offsets[name]-100);await render();});
    previous.disabled=offsets[name]===0;
    const next=button("Next",async()=>{if(dirty.size&&!confirm("Leave without saving your draft edits?"))return;dirty.clear();offsets[name]+=100;await render();});
    next.disabled=items.length<100;
    root.append(el("div",{class:"actions"},previous,el("span",{},"Page "+(offsets[name]/100+1)),next));
}
async function pollOperation(){
    if(!loggedIn||!operationId)return;
    const job=await api("/api/jobs/"+operationId);
    const counts=job.result?.counts?": "+Object.entries(job.result.counts).map(([key,value])=>key+" "+value).join(", "):"";
    document.getElementById("operation-status").textContent="Job #"+job.id+" · "+job.status+counts+(job.error?" · "+job.error:"");
    if(["complete","failed","canceled"].includes(job.status))operationId=null;
}
const loaders={Dashboard:dashboard,Contacts:contactsView,Companies:companiesView,Review:reviewView,Queue:queueView,Tracking:trackingView,Targets:targetsView,Settings:settingsView,Jobs:jobsView};
async function loginScreen(){
    loggedIn=false;epoch++;
    content.setAttribute("aria-busy","false");
    const password=input("","password");password.autocomplete="current-password";
    content.replaceChildren(card("Owner sign in",field("Password",password),button("Sign in",async()=>{const r=await api("/api/login","POST",{password:password.value});csrf=r.csrf;await boot();},"primary")));
}
async function boot(){
    const session=await api("/api/session");csrf=session.csrf;
    nav.replaceChildren(...pages.map(page=>{const b=button(page,()=>{reviewFocus=null;return navigate(page);});b.setAttribute("aria-current",page===view?"page":"false");return b;}));
    const logout=document.getElementById("logout");logout.hidden=!session.owner_mode;
    logout.onclick=async()=>{try{
        await Promise.allSettled([...pendingWrites]);
        if(dirty.size&&!confirm("Sign out without saving your edits?"))return;
        await api("/api/logout","POST",{});dirty.clear();await boot();
    }catch(e){toast(e.message,true);}};
    if(!session.authenticated){await loginScreen();return;}
    loggedIn=true;
    const recovered=await api('/api/jobs');
    operationId=recovered.find(j=>['pending','running'].includes(j.status))?.id||null;
    await render();
}
window.addEventListener("beforeunload",event=>{if(dirty.size){event.preventDefault();event.returnValue="";}});
setInterval(()=>{pollOperation().catch(error=>toast(error.message,true));if(loggedIn&&view==="Jobs"&&!dirty.size)render();},4000);
boot().catch(error=>{content.replaceChildren(el("div",{class:"error",role:"alert"},error.message));content.setAttribute("aria-busy","false");});
