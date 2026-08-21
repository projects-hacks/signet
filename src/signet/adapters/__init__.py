"""Vendor implementations of the ports.

One module per vendor. Each owns its own timeouts, retries, budget and caching,
so callers never reason about a vendor's limits. Nothing here is imported by
core, verify or issue.
"""
