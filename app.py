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
            <div class="kpi-row">
                <div class="kpi-card">
                    <div class="kpi-label"><span class="status-dot status-warning"></span> PENDING REVIEW</div>
                    <div class="kpi-value">24</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label"><span class="status-dot status-success"></span> APPROVED</div>
                    <div class="kpi-value">12</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label"><span class="status-dot status-neutral"></span> SENT</div>
                    <div class="kpi-value">104</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label"><span class="status-dot status-success"></span> REPLIED</div>
                    <div class="kpi-value">18</div>
                </div>
            </div>
            
            <div class="table-container" style="margin-top: 16px;">
                <table>
                    <thead>
                        <tr>
                            <th>Variant</th>
                            <th class="col-num">Sent</th>
                            <th class="col-num">Replied</th>
                            <th class="col-num">Interviews</th>
                            <th class="col-num">Reply %</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Software Engineer (Backend)</td>
                            <td class="col-num">45</td>
                            <td class="col-num">8</td>
                            <td class="col-num">2</td>
                            <td class="col-num">17.8</td>
                        </tr>
                        <tr>
                            <td>Data Scientist</td>
                            <td class="col-num">32</td>
                            <td class="col-num">5</td>
                            <td class="col-num">1</td>
                            <td class="col-num">15.6</td>
                        </tr>
                        <tr>
                            <td>Unassigned</td>
                            <td class="col-num">27</td>
                            <td class="col-num">5</td>
                            <td class="col-num">0</td>
                            <td class="col-num">18.5</td>
                        </tr>
                    </tbody>
                </table>
            </div>
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
