import streamlit as st
import requests
import jwt
from datetime import datetime
import plotly.express as px
from database import oracle, chatwoot
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import unicodedata
import io
import xlsxwriter
import extra_streamlit_components as stx
import os
import bcrypt
import pytz
import plotly.graph_objects as go

EMAILS_INICIO = [
    "pablo.ti@caiuas.com.br",
]


def render():
    st.title("BI - Caiuás")
    st.write("Bem-vindo ao dashboard de BI da Caiuás!")
    st.write("Use o menu lateral para navegar entre as diferentes seções.")
    