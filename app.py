from flask import Flask, jsonify, request, send_from_directory
import json
import db, config, contacts, tracker, reviewer, composer, sender, replies, suppression

app = Flask(__name__, static_folder='static', template_folder='templates')

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/stats')
def api_stats():
    return jsonify({
        "summary": tracker.pipeline_summary(),
        "stats": tracker.stats()
    })

@app.route('/api/contacts')
def api_list_contacts():
    all_contacts = []
    comps = contacts.list_companies()
    for c in comps:
        for ct in contacts.list_contacts(c["id"]):
            ct["company_name"] = c["name"]
            all_contacts.append(ct)
    return jsonify(all_contacts)

@app.route('/api/companies')
def api_list_companies():
    return jsonify(contacts.list_companies())

@app.route('/api/companies', methods=['POST'])
def api_add_company():
    data = request.json
    cid = contacts.add_company(data["name"], data.get("domain"), data.get("job_url"), data.get("job_text"), data.get("notes"))
    return jsonify({"id": cid})

@app.route('/api/contacts', methods=['POST'])
def api_add_contact():
    data = request.json
    cid = contacts.add_contact(data["company_id"], data["email"], data.get("name"), data.get("title"), data.get("source"))
    return jsonify({"id": cid})

@app.route('/api/contacts/import', methods=['POST'])
def api_import_csv():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    import tempfile
    import os
    from werkzeug.utils import secure_filename
    
    filename = secure_filename(file.filename)
    tmp_path = os.path.join(tempfile.gettempdir(), filename)
    file.save(tmp_path)
    
    try:
        summary = contacts.import_csv(tmp_path)
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.route('/api/compose', methods=['POST'])
def api_compose():
    data = request.json
    try:
        contact_id = data["contact_id"]
        # Prevent drafting duplicates
        from repository import EmailRepository
        existing = EmailRepository.get_by_contact_id(contact_id)
        if any(e["status"] in ["pending_review", "approved", "sent"] for e in existing):
            return jsonify({"error": "An active email already exists for this contact."}), 400
            
        eid = composer.compose_and_store(data["company_id"], contact_id, data.get("resume_variant_id"))
        return jsonify({"id": eid})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/review')
def api_review_list():
    return jsonify(reviewer.list_pending())

@app.route('/api/review/<int:email_id>', methods=['POST'])
def api_review_action(email_id):
    data = request.json
    action = data.get("action")
    if action == "approve":
        reviewer.approve(email_id)
    elif action == "reject":
        reviewer.reject(email_id)
    elif action == "edit":
        reviewer.edit(email_id, subject=data.get("subject"), body=data.get("body"), hook=data.get("hook"))
    return jsonify({"success": True})

@app.route('/api/tracking')
def api_tracking_list():
    from repository import EmailRepository
    rows = EmailRepository.get_all_tracked_emails()
    return jsonify([dict(r) for r in rows])

@app.route('/api/tracking/due')
def api_tracking_due():
    return jsonify(tracker.due_for_follow_up())

@app.route('/api/tracking/<int:email_id>/mark', methods=['POST'])
def api_tracking_mark(email_id):
    status = request.json.get("status")
    # map status
    if status == "replied": tracker.mark_replied(email_id)
    elif status == "ghosted": tracker.mark_ghosted(email_id)
    elif status == "bounced": tracker.mark_bounced(email_id)
    elif status == "interview_scheduled": tracker.mark_interview_scheduled(email_id)
    elif status == "interview_completed": tracker.mark_interview_completed(email_id)
    elif status == "offer": tracker.mark_offer(email_id)
    elif status == "no_offer": tracker.mark_no_offer(email_id)
    return jsonify({"success": True})

@app.route('/api/tracking/<int:email_id>/followup', methods=['POST'])
def api_tracking_followup(email_id):
    try:
        from repository import EmailRepository
        original = EmailRepository.get_by_id(email_id)
        if not original:
            return jsonify({"error": "Original email not found"}), 404
        
        # Prevent drafting duplicate followups for the same email
        existing_emails = EmailRepository.get_by_contact_id(original["contact_id"])
        if any(e["follow_up_to_email_id"] == email_id for e in existing_emails):
            return jsonify({"error": "A follow-up for this email already exists."}), 400

        eid = composer.compose_follow_up_and_store(email_id)
        return jsonify({"id": eid})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/send', methods=['POST'])
def api_send_batch():
    summary = sender.run_send_batch()
    return jsonify({"summary": summary})

@app.route('/api/check_replies', methods=['POST'])
def api_check_replies():
    try:
        matches = replies.check_replies(dry_run=False)
        return jsonify({"matches": matches})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    db.init_db()
    app.run(debug=True, port=5000)
