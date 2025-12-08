from typing import Callable, Dict, List, Any, Iterable, Tuple
from parsel import Selector as ParselSelector
from collections import Counter, defaultdict
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta, date
from difflib import SequenceMatcher
from urllib.parse import urlparse
from lxml import html as html_lx
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from lxml import html as lh
from textwrap import dedent
from string import Template
from pprint import pprint
import html as std_html
from lxml import etree
import jsbeautifier
import itertools
import requests
import locale
import json
import time
import re
import os

# Глобальные переменные
message_global = []
current_apsp_version = "0.1"

# Глобальные модули
from module_logging import * 