# handlers/job_scheduler.py
import html

class JobSchedulerHandler:
    def __init__(self, scheduler_service):
        self.scheduler_service = scheduler_service

    def list_jobs(self, handler):
        jobs = self.scheduler_service.scheduler.get_jobs()
        rows = []
        for j in jobs:
            next_run = j.next_run_time.isoformat() if j.next_run_time else "-"
            rows.append(
                f"<tr><td>{html.escape(j.id)}</td>"
                f"<td>{html.escape(j.name or '')}</td>"
                f"<td>{html.escape(str(j.trigger))}</td>"
                f"<td>{next_run}</td></tr>"
            )

        body = f"""
        <html><head><title>Scheduled Jobs</title></head>
        <body>
          <h1>Scheduled Jobs</h1>
          <table border="1" cellpadding="5" cellspacing="0">
            <tr><th>ID</th><th>Name</th><th>Trigger</th><th>Next run</th></tr>
            {''.join(rows) if rows else '<tr><td colspan="4">(none)</td></tr>'}
          </table>
          <p><a href="/">Back</a></p>
        </body></html>
        """
        handler.send_response(200)
        handler.send_header('Content-type', 'text/html')
        handler.end_headers()
        handler.wfile.write(body.encode('utf-8'))

    def schedule_job(self, handler, form_data):
        body = """
        <html><body>
          <h1>Not Implemented</h1>
          <p>Adding jobs from the UI is not implemented yet.</p>
          <a href="/">Back</a>
        </body></html>
        """
        handler.send_response(501)
        handler.send_header('Content-type', 'text/html')
        handler.end_headers()
        handler.wfile.write(body.encode('utf-8'))

