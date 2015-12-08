import os
import redis
import logging

from datetime import datetime

from rq import Worker, Queue, Connection
from rq_scheduler import Scheduler

INTERVAL = 60.0
listen = ['high', 'default', 'low']


redis_url = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')
if not redis_url:
    raise RuntimeError('Set up Redis To Go first.')
conn = redis.from_url(redis_url)

scheduler = Scheduler(connection=conn, interval=INTERVAL)


def periodic_schedule():
    """Enqueue in rq all periodically executed jobs"""
    from nucleus.nucleus import jobs

    logging.warning("Setting up periodical jobs:\n- {}".format("\n- ".join(j[0] for j in jobs.periodical)))

    for job in jobs.periodical:
        jid = jobs.job_id("periodical", job[0])
        if jid in scheduler:
            scheduler.cancel(jid)

        scheduler.schedule(
            scheduled_time=datetime.utcnow(),
            func=getattr(jobs, job[0]),
            interval=job[1],
            result_ttl=job[1] + 5,
            id=jid,
        )


if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()

    scheduler.run()
