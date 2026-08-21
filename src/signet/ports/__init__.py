"""Protocols for every external capability.

core, verify and issue import from here and never from adapters. Ports are
defined in domain terms, so an adapter cannot leak a vendor concept upward, and
the whole pipeline runs against fakes with no network.
"""
