import os
import streamlit.components.v1 as components

_component_func = components.declare_component(
    "qr_scanner",
    path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend"),
)

def qr_scanner(key=None):
    return _component_func(key=key, default=None)
