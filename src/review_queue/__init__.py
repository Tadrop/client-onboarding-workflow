"""Account-manager review queue.

The HTTP surface is in `routes.py`; this package keeps the schemas inline.
The only way for an external client email to actually send is for an AM to
hit `/reviews/{id}/approve` here.
"""
