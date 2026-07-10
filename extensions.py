from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# In-memory storage by default. With gunicorn --workers 2, each worker
# tracks its own counter — so the real ceiling is closer to 2x whatever
# limit is set below. Fine as a blunt deterrent against bursts; if you
# add Redis later (e.g. for the analysis cache), point storage_uri at it
# here for an exact, worker-shared limit.
limiter = Limiter(key_func=get_remote_address)