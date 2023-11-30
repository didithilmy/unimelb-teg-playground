import os
import importlib
from pathlib import Path
import streamlit as st

def main():
    app_state = st.experimental_get_query_params()
    app_key = app_state.get("app", False)
    if not app_key:
        st.markdown("# App not found")
        return
    app_key = app_key[0]

    app_map = {}
    for fname in os.listdir('apps/'):
        if fname.lower().endswith('.py'):
            app_name = Path(fname).stem
            module = importlib.import_module("apps." + app_name)
            app_map[app_name] = module.app

    app = app_map.get(app_key)
    if app is None:
        st.markdown("# App not found")
    else:
        app()

main()