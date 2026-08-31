from flask import Flask, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Outreacher Terminal</title>
    <link rel="stylesheet" href="/static/style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
</head>
<body>
    <div class="sidebar">
        <div class="nav-brand">OUTREACH_</div>
        <nav>
            <a href="#" class="nav-item active">Dashboard</a>
            <a href="#" class="nav-item">Contacts</a>
            <a href="#" class="nav-item">Review Queue</a>
            <a href="#" class="nav-item">Tracking</a>
        </nav>
    </div>
    <div class="main-content">
        <header>
            <h1>Dashboard</h1>
        </header>
        <div class="content-grid">
            <!-- Content will go here -->
        </div>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
