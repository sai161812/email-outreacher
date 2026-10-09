"use strict";
const content=document.getElementById("content"),nav=document.getElementById("navigation");
let csrf="",view="Dashboard",epoch=0,dirty=new Set(),contactsOffset=0,contactSearch="",settingsCache=null,loggedIn=false;
const pendingWrites=new Set();
const offsets={Companies:0,Review:0,Queue:0,Tracking:0};
let operationId=null;
const pages=["Dashboard","Contacts","Companies","Review","Queue","Tracking","Settings","Jobs"];
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
async function api(path,method="GET",data=null){
    const options={method,headers:{}};
    if(method!=="GET"){options.headers["X-CSRF-Token"]=csrf;options.headers["Idempotency-Key"]=crypto.randomUUID();}
    if(data instanceof FormData)options.body=data;
    else if(data!==null){options.headers["Content-Type"]="application/json";options.body=JSON.stringify(data);}
    const task=(async()=>{
        const response=await fetch(path,options);
        let result;try{result=await response.json();}catch{throw new Error("Server returned an unreadable response. Check the connection.");}
        if(!response.ok){if(response.status===401)await loginScreen();throw new Error(result.error||"Request failed");}
        return result;
    })();
    if(method!=="GET")pendingWrites.add(task);
    try{return await task;}finally{pendingWrites.delete(task);}
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
    const job=await api(path,"POST",data);
    operationId=job.id;
    toast("Operation queued. See Jobs for progress and results.");
    document.getElementById("operation-status").textContent="Job #"+job.id+" is "+job.status+". A worker processes queued operations.";
    return job;
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
    const root=el("div",{},title("Dashboard",button("Refresh",render),button("Preview send batch",()=>queued("/api/send",{dry_run:true})),button("Send approved batch",()=>queued("/api/send"),"primary"),button("Check replies",()=>queued("/api/check_replies"))));
    const missing=Object.entries(setup.readiness).filter(([,ready])=>!ready).map(([key])=>key);
    if(missing.length)root.append(el("p",{class:"notice"},"Setup needed: "+missing.join(", ")+". Open Settings before drafting or sending."));
    root.append(el("p",{class:"notice"},"Daily remaining capacity: "+setup.configuration.daily_remaining+" of "+setup.configuration.daily_cap+". Outstanding uncertain attempts consume capacity."));
    root.append(el("div",{class:"grid"},["pending_review","approved","sent","replied"].map(key=>card(key.replaceAll("_"," "),el("div",{class:"metric"},data.summary[key]||0)))));
    root.append(card("Resume performance",el("p",{class:"muted"},"Rates count sent messages, including follow-ups."),table(["Resume","Sent","Replies","Interviews","Offers","Reply rate"],data.stats.by_variant.map(v=>el("tr",{},[v.name,v.sent,v.replied,v.interviews,v.offers,v.reply_rate+"%"].map(value=>cell(value)))))));
    return root;
}
async function contactsView(){
    const [people,companies,setup]=await Promise.all([api("/api/contacts?limit=100&offset="+contactsOffset+"&search="+encodeURIComponent(contactSearch)),api("/api/companies"),api("/api/settings")]);
    const draftResume=select([["auto","Automatic match"],["none","No resume"],...setup.resumes.map(r=>[r.id,r.name])],"auto");
    function draftFor(person){
        const data={company_id:person.company_id,contact_id:person.id};
        if(draftResume.value!=="auto")data.resume_variant_id=draftResume.value==="none"?null:Number(draftResume.value);
        return queued("/api/compose",data);
    }
    const search=input(contactSearch);search.setAttribute("aria-label","Search contacts");
    const file=el("input",{type:"file",accept:".csv","aria-label":"Import contacts CSV"});
    file.addEventListener("change",async()=>{if(!file.files.length)return;const form=new FormData();form.append("file",file.files[0]);try{const r=await api("/api/contacts/import","POST",form);toast(r.contacts_created+" contacts added; "+r.duplicates_skipped+" duplicates skipped.");if(r.errors.length)toast(r.errors.map(e=>"Row "+e.row+": "+e.error).join("; "),true);await render();}catch(e){toast(e.message,true);}finally{file.value="";}});
    const root=el("div",{},title("Contacts",button("Add contact",()=>contactForm(companies)),button("Search",async()=>{contactSearch=search.value;contactsOffset=0;await render();})),field("Search name, company or email",search),field("Import CSV",file));
    root.append(field("Resume for new drafts",draftResume));
    root.append(table(["Company","Name","Email","Actions"],people.map(p=>el("tr",{},cell(p.company_name,true),cell(p.name||"—",true),cell(p.email),cell(el("div",{class:"actions"},button("Draft",()=>draftFor(p)),button("Edit",()=>contactForm(companies,p)),button("Check DNS",async()=>{const result=await api("/api/contacts/"+p.id+"/validate","POST",{});toast((result.warning||"Domain accepts mail in DNS")+". "+result.note,!!result.warning);})))))));
    if(!people.length)root.append(el("p",{},"No contacts found. Add a company first, or import the sample CSV."));
    root.append(el("div",{class:"actions"},button("Previous",async()=>{contactsOffset=Math.max(0,contactsOffset-100);await render();}),button("Next",async()=>{if(people.length===100){contactsOffset+=100;await render();}})));
    return root;
}
function contactForm(companies,person=null){
    if(!companies.length){toast("Add a company first in Companies.",true);return;}
    const company=select(companies.map(c=>[c.id,c.name]),person?.company_id||companies[0].id),name=input(person?.name),email=input(person?.email,"email"),role=input(person?.title),source=input(person?.source);
    company.disabled=!!person;
    const body=el("div",{},field("Company",company),field("Name",name),field("Email",email),field("Role / title",role),field("Source",source));
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
async function reviewView(){
    const [drafts,setup]=await Promise.all([api("/api/review?limit=100&offset="+offsets.Review),api("/api/settings")]);
    const root=el("div",{},title("Review queue"));
    if(!drafts.length)root.append(el("p",{},"No drafts awaiting review."));
    for(let draft of drafts){
        let writing=false,editSerial=0,save,reject;
        const subject=input(draft.subject),hook=input(draft.hook),body=el("textarea",{value:draft.body||"",rows:8});
        const variant=select([[0,"No resume"],...setup.resumes.map(r=>[r.id,r.name])],draft.resume_variant_id||0);
        const warnings=el("p",{class:"warning"},draft.qc_warnings||"Review facts, recipient, content and resume before approving.");
        const status=el("p",{class:"muted"},"Revision "+draft.revision+" · Pending review");
        const approve=button("Approve saved revision",()=>writeReview(async()=>{await api("/api/review/"+draft.id,"POST",{action:"approve",revision:draft.revision});dirty.delete(draft.id);section.remove();toast("Approved. Available in Queue.");},true),"primary",()=>writing||dirty.has(draft.id));
        const section=card(draft.company_name+" · "+draft.contact_email,status,field("Subject",subject),field("Research hook",hook),field("Body",body),field("Resume choice",variant),warnings);
        function syncActions(){save.disabled=writing;reject.disabled=writing;approve.disabled=writing||dirty.has(draft.id);}
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
        const asset=el("div",{});
        function showAsset(){
            const selected=setup.resumes.find(r=>r.id===Number(variant.value));
            asset.replaceChildren(el("p",{class:"muted"},"Delivery mode: "+setup.configuration.resume_mode));
            if(!selected)asset.append(el("p",{},"No resume selected."));
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
        section.append(el("div",{class:"actions"},save,approve,reject));
        root.append(section);
    }
    paginate(root,"Review",drafts);return root;
}
async function queueView(){
    const items=await api("/api/queue?limit=100&offset="+offsets.Queue);
    const root=el("div",{},title("Approved queue",button("Send approved batch",()=>queued("/api/send"),"primary")),el("p",{},"Only the approved revision and attachment may send. Caps, suppression and send windows are checked again at delivery."),
        table(["Company","Recipient","Subject","Actions"],items.map(r=>el("tr",{},cell(r.company_name,true),cell(r.contact_email),cell(r.subject,true),cell(button("Return to review",async()=>{await api("/api/review/"+r.id,"POST",{action:"edit",revision:r.revision});await render();}))))));
    paginate(root,"Queue",items);return root;
}
async function trackingView(){
    const [tracked,due,attempts]=await Promise.all([api("/api/tracking?limit=100&offset="+offsets.Tracking),api("/api/tracking/due"),api("/api/attempts")]);
    const root=el("div",{},title("Tracking",button("Refresh",render),button("Check replies",()=>queued("/api/check_replies"))));
    root.append(card("Due for follow-up",table(["Company","Recipient","Actions"],due.map(r=>el("tr",{},cell(r.company_name,true),cell(r.contact_email),cell(button("Draft follow-up",()=>queued("/api/tracking/"+r.id+"/followup"))))))));
    const statuses=["replied","ghosted","bounced","interview_scheduled","interview_completed","offer","no_offer"];
    root.append(table(["Company","Recipient","Status","Sent","Update"],tracked.map(r=>{
        const choice=select(statuses.map(s=>[s,s.replaceAll("_"," ")]),r.status);
        choice.setAttribute("aria-label","Outcome for email #"+r.id);
        const action=el("div",{class:"actions"});
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
async function settingsView(){
    const setup=await api("/api/settings");settingsCache=setup;
    const readiness=el("p",{},Object.entries(setup.readiness).map(([key,ready])=>key+": "+(ready?"ready":"needed")).join(" · "));
    const root=el("div",{},title("Settings"),card("Readiness",readiness,
        el("p",{class:"muted"},"Model: "+setup.configuration.model+" · Timezone: "+setup.configuration.timezone+" · Resume mode: "+setup.configuration.resume_mode)));
    const fields={};for(const key of ["full_name","email","phone","linkedin_url","github_url","portfolio_url"])fields[key]=input(setup.profile?.[key],key.includes("url")?"url":key==="email"?"email":"text");
    const context=el("textarea",{value:setup.candidate_context,rows:6});
    let editSerial=0;
    for(const node of [...Object.values(fields),context])node.addEventListener("input",()=>{editSerial++;dirty.add("settings");});
    const resumeList=el("div",{}),suppressionList=el("div",{});
    let listSerial=0;
    function showLists(data){
        resumeList.replaceChildren(table(["Name","Keywords","Link"],data.resumes.map(r=>el("tr",{},cell(r.name,true),cell(r.keywords,true),cell(r.resume_url?safeLink(r.resume_url,"Open resume link"):"PDF registered")))));
        suppressionList.replaceChildren(table(["Address","Reason","Actions"],data.suppressions.map(r=>el("tr",{},cell(r.email),cell(r.reason,true),cell(button("Remove suppression",async()=>{await api("/api/suppressions","DELETE",{email:r.email});await refreshLists();}))))));
    }
    async function refreshLists(){const serial=++listSerial;const data=await api("/api/settings");if(serial===listSerial){settingsCache=data;showLists(data);}}
    showLists(setup);
    root.append(card("Profile and verified candidate facts",Object.entries(fields).map(([key,node])=>field(key.replaceAll("_"," "),node)),field("Candidate facts — include only truthful skills and achievements",context),
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
    const jobs=await api("/api/jobs");
    return el("div",{},title("Jobs",button("Refresh",render)),el("p",{class:"notice"},"Operations remain queued until the background worker is running. This view refreshes automatically."),
        jobs.map(j=>card("#"+j.id+" · "+j.kind+" · "+j.status,j.error?el("p",{class:"error"},j.error):null,j.result?.counts?el("p",{},Object.entries(j.result.counts).map(([name,count])=>name+": "+count).join(" · ")):null,el("details",{open:j.status==="failed"?"":undefined},el("summary",{},"Results"),el("pre",{},j.result?JSON.stringify(j.result,null,2):"No result yet")))));
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
    if(["complete","failed"].includes(job.status))operationId=null;
}
const loaders={Dashboard:dashboard,Contacts:contactsView,Companies:companiesView,Review:reviewView,Queue:queueView,Tracking:trackingView,Settings:settingsView,Jobs:jobsView};
async function loginScreen(){
    loggedIn=false;epoch++;
    content.setAttribute("aria-busy","false");
    const password=input("","password");password.autocomplete="current-password";
    content.replaceChildren(card("Owner sign in",field("Password",password),button("Sign in",async()=>{const r=await api("/api/login","POST",{password:password.value});csrf=r.csrf;await boot();},"primary")));
}
async function boot(){
    const session=await api("/api/session");csrf=session.csrf;
    nav.replaceChildren(...pages.map(page=>{const b=button(page,()=>navigate(page));b.setAttribute("aria-current",page===view?"page":"false");return b;}));
    const logout=document.getElementById("logout");logout.hidden=!session.owner_mode;
    logout.onclick=async()=>{try{
        await Promise.allSettled([...pendingWrites]);
        if(dirty.size&&!confirm("Sign out without saving your edits?"))return;
        await api("/api/logout","POST",{});dirty.clear();await boot();
    }catch(e){toast(e.message,true);}};
    if(!session.authenticated){await loginScreen();return;}
    loggedIn=true;
    await render();
}
window.addEventListener("beforeunload",event=>{if(dirty.size){event.preventDefault();event.returnValue="";}});
setInterval(()=>{pollOperation().catch(error=>toast(error.message,true));if(loggedIn&&view==="Jobs"&&!dirty.size)render();},4000);
boot().catch(error=>{content.replaceChildren(el("div",{class:"error",role:"alert"},error.message));content.setAttribute("aria-busy","false");});
