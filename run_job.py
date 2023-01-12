import schedule
from schedule import every, repeat
import functools
import time
import notion_backup


def catch_exceptions(cancel_on_failure=False):
    def catch_exceptions_decorator(job_func):
        @functools.wraps(job_func)
        def wrapper(*args, **kwargs):
            try:
                return job_func(*args, **kwargs)
            except:
                import traceback
                print(traceback.format_exc())
                if cancel_on_failure:
                    return schedule.CancelJob

        return wrapper

    return catch_exceptions_decorator


@catch_exceptions(cancel_on_failure=True)
@repeat(every().day.at("03:00"))
def notion_job():
    print("start notion_job")
    notion_backup.run_retry()


if __name__ == '__main__':
    print('run_job start')

    while True:
        schedule.run_pending()
        time.sleep(3)