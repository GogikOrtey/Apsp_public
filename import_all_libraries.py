from typing import Callable, Dict, List, Any, Iterable, Tuple
from collections import Counter, defaultdict
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import urlparse
from lxml import html as html_lx
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from lxml import html as lh
from string import Template
from pprint import pprint
import html as std_html
from lxml import etree
import itertools
import requests
import json
import time
import re
import os