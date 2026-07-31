import sqlite3
from datetime import datetime

c = sqlite3.connect(r"D:/NIUBI/SaaS-HZ_WEB_Demo/backend/data/crosshub.db")
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
c.execute(
    """
    update agent_task
    set status='failed', finished_at=?, error_code='EXE_SMOKE_RESET',
        error_message='reset stuck probe before exe retest'
    where tenant_id=5 and status in ('pending','running')
      and created_at>='2026-07-28 10:15:00'
    """,
    (now,),
)
c.execute(
    """
    update temu_crawl_job
    set status='failed', finished_at=?, error_code='EXE_SMOKE_RESET',
        error_message='reset before exe retest'
    where id='3328cec7-6bbd-4a12-9d84-2651441d298a'
    """,
    (now,),
)
c.commit()
print("ok", c.total_changes)
