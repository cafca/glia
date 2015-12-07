import os
import redis
import logging

from datetime import timedelta, datetime

from rq import Worker, Queue, Connection
from rq_scheduler import Scheduler

INTERVAL = 15.0
listen = ['high', 'default', 'low']
job_ids = [
    "periodic-refresh_attention_cache",
]


redis_url = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')
if not redis_url:
    raise RuntimeError('Set up Redis To Go first.')
conn = redis.from_url(redis_url)


scheduler = Scheduler(connection=conn, interval=INTERVAL)


def periodic_schedule():
    """Enqueue in rq all periodically executed jobs"""
    from nucleus.nucleus import jobs

    for jid in job_ids:
        if jid in scheduler:
            logging.warning("Cancelling " + jid)
            scheduler.cancel(jid)

        logging.warning("Scheduling " + jid)
        scheduler.schedule(
            scheduled_time=datetime.utcnow() + timedelta(seconds=5),
            func=jobs.refresh_attention_cache,
            interval=10,
            result_ttl=0,
            id=jid,
        )
        logging.warning(scheduler.get_jobs())


if __name__ == '__main__':
    from glia import create_app

    app = create_app()
    with app.app_context():
        with Connection(conn):
            worker = Worker(map(Queue, listen))
            worker.work()

        scheduler.run()
