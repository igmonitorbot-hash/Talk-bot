import os
import logging
import threading
import asyncio
import tempfile
import random
from io import BytesIO
from http.server import HTTPServer, BaseHTTPRequestHandler
from PIL import Image
import cv2
from google import genai
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------------------------------------------------------------------
# LOGGING SETUP
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ENVIRONMENT VARIABLES & CLIENT INIT
# ---------------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN:
    raise ValueError("Missing BOT_TOKEN environment variable.")
if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY environment variable. Please set it in Render.")

# Initialize standard Gemini Client using new google-genai SDK
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-3.1-flash-lite"

# ---------------------------------------------------------------------------
# BOT STICKERS LIBRARY WITH CONTEXT LABELS
# ---------------------------------------------------------------------------
# Each sticker is tagged with a category so the bot can pick a contextually relevant one.
BOT_STICKERS = [
    {"id": "CAACAgIAAxkBAAICbGqBYK0ZNBgGL7zVvdSiwmTV9JMcAAJQeAACNP85Se57543TR05nPQQ", "tags": ["tease", "hot", "breast", "naughty"]},
    {"id": "CAACAgIAAxkBAAICbmqBYK1TzvYH6sO7-5-PaInP2jQHAAJFZAACf345SfmSXNO9tnzqPQQ", "tags": ["hot", "breast", "sensual", "naughty"]},
    {"id": "CAACAgIAAxkBAAICcGqBYK5QzcvsXdAV0woUQCFepmxuAAIZaQACeEg5SfqXttO-Pj8kPQQ", "tags": ["kiss", "love", "romantic"]},
    {"id": "CAACAgIAAxkBAAICcmqBYK6p8kxaXv7_K7Bgu4S6P8qGAALJdgACAYw5SVVwxYkpq5OIPQQ", "tags": ["flirt", "wink", "playful"]},
    {"id": "CAACAgIAAxkBAAICfGqBYLCNTbaEVnKvsNs3KEaJw9gMAALHggACsoMwSboGrZLD1f7TPQQ", "tags": ["hot", "tease", "naughty"]},
    {"id": "CAACAgIAAxkBAAICfWqBYLB1II3P_1q7HF-mA-UflUbEAAJiZAACNwABOElL7xSKng22lT0E", "tags": ["happy", "cute", "flirt"]},
    {"id": "CAACAgIAAxkBAAICfmqBYLBCarfZx-wmMZmawHuCxUz7AAK5bAACt3E5SYCaDN7pp0YAAT0E", "tags": ["hot", "naughty", "breast"]},
    {"id": "CAACAgIAAxkBAAICf2qBYLB31WnIev4K_hHWUNxkYTKXAAKCaAACIaM5ScqK7SbtRX-VPQQ", "tags": ["playful", "tease"]},
    {"id": "CAACAgIAAxkBAAICgGqBYLA-NKhMsXEJe8u0kP9Ayr4UAAL1ZAAC_8U5STa4ykWtTdmMPQQ", "tags": ["love", "romantic"]},
    {"id": "CAACAgIAAxkBAAICgWqBYLCCdJScnkkTqV90vtE6rfgcAALrcwACj7oxSTnRHWEueYnUPQQ", "tags": ["flirt", "wink"]},
    {"id": "CAACAgIAAxkBAAICgmqBYLB42rBPzZ4QFoG0Wa80AAFcQQACfmkAAjX6OEnd-eL8hZ-boz0E", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICg2qBYLE0UF7kHYeon7OZyUfrVA4AA_1xAAIlJTlJ7D_hhpNbUdA9BA", "tags": ["breast", "hot", "tease"]},
    {"id": "CAACAgIAAxkBAAIChWqBYLF2eSP4EVSm4t28xuS0gFNBAALrdAACM8cwSbjMKKSL2wNaPQQ", "tags": ["playful", "cute"]},
    {"id": "CAACAgIAAxkBAAICh2qBYLGH1v6BdCeU5u4XCsSj9vkAA9JpAAL_ZzhJS72rTTcl_cY9BA", "tags": ["hot", "naughty", "breast"]},
    {"id": "CAACAgIAAxkBAAICiGqBYLG8glL2kkz7u8wH2cg4H1qhAAJ9bAACYkQ4SVB--71CGX4VPQQ", "tags": ["kiss", "romantic"]},
    {"id": "CAACAgIAAxkBAAICimqBYLH-cmt0ZqXPWlysdlklH11aAAJyeAACMnUwSQ6xPX8LsxXBPQQ", "tags": ["flirt", "hot"]},
    {"id": "CAACAgIAAxkBAAICjGqBYLEFKitmP1h7GcTHPx3uFdkBAALuZgAC7l45SY9zaSClZqIrPQQ", "tags": ["hot", "tease"]},
    {"id": "CAACAgIAAxkBAAIClWqBYLT5dhfbh6JAR-Etx34DSZ7JAALdegACR_kwSb1omU_RR2_7PQQ", "tags": ["playful", "cute"]},
    {"id": "CAACAgIAAxkBAAICl2qBYLRAfbExD1M3l8xpkEN8gFTDAAIafQACh-kxSbYtyczDISuWPQQ", "tags": ["flirt", "wink"]},
    {"id": "CAACAgIAAxkBAAICmGqBYLT4bYSeBJF4cvQaqrSeREB2AAKsegACbkgxSdezHxTf_JZvPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICmWqBYLSLc7i4pAABWQnp1JXdJpuCWwACg2sAAnaOOUmXvJxVzbkoRD0E", "tags": ["cute", "love"]},
    {"id": "CAACAgIAAxkBAAICmmqBYLSOr_RYbLwoBCmjlYQqMYpjAAL5bwACPjo4SQjX6UZjd0ykPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAICm2qBYLQzinETCInGYPfeeHYjT_xjAALqdgACOgo5SU9o-iJXvjExPQQ", "tags": ["tease", "playful"]},
    {"id": "CAACAgIAAxkBAAICnGqBYLQ-FDfXwiyirnDSmlqUUA4lAAIicAACbXI5SeacfE0DwZJ8PQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICnWqBYLTbFRbL0aM40F8RSblXrly2AALPawACicU4SX0NJKAb9aRcPQQ", "tags": ["flirt", "wink"]},
    {"id": "CAACAgIAAxkBAAICnmqBYLRviu5XiQABv_uAmfLQcT76WAAC5nQAAmyEOEkGikosTM9aCz0E", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAICoWqBYLQQKjh1lAQLBWQCkw1YUa79AAJ6dQACrm0wSZ5HziQF1F2lPQQ", "tags": ["love", "romantic"]},
    {"id": "CAACAgIAAxkBAAIComqBYLUroKCjFT1j63XMuBecmyMQAAJjZQAC-hs4SfbpiqO8rlL3PQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICpGqBYLUW0EIVhpRmus40aznn5pwiAAIHZwACAZw4SfiXRrCYMSzlPQQ", "tags": ["flirt", "playful"]},
    {"id": "CAACAgIAAxkBAAICpWqBYLVz9WlKSoEuuR4r4PAS9Yf1AAKvbgACoGg4SbyUcOVnYIGyPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAICpmqBYLXQ4SwfO2Ijt4NX0zwt-spFAAJsZgAClgk5SYRhc2HlalDZPQQ", "tags": ["hot", "tease"]},
    {"id": "CAACAgIAAxkBAAICqGqBYLV6u1kqbZTSF7G1-7B_pQAB9AACCHwAAtP7MEmxXQMvTio2yj0E", "tags": ["cute", "playful"]},
    {"id": "CAACAgIAAxkBAAICq2qBYLVIzQQw06TWewyzTvME21tvAAI-YwACHpY4SahlEpj8x2klPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICrWqBYLbuprgJX1MdVFuboueYRKvmAALfbwACmMU4ScVuFX8NX0dbPQQ", "tags": ["love", "kiss"]},
    {"id": "CAACAgIAAxkBAAICr2qBYLbmsEPiCc4-NZCITBv2D8hHAAJ5awACiJw5SQvz4mc3QOkOPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAICtGqBYLeZRWe54nJfNnXEAAHj2PU-TAACB3IAAgfUMEmwUzswtOTGkT0E", "tags": ["playful", "wink"]},
    {"id": "CAACAgIAAxkBAAICtWqBYLcQpFGhcl4R6mm2xccNAthLAAJzagACMvQ4STBwKv9vzHvSPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICt2qBYLdXkiBSz283JJkrtgg9ljtoAALtaAACgow4SbRzr1biidY0PQQ", "tags": ["tease", "hot"]},
    {"id": "CAACAgIAAxkBAAICuGqBYLfUNlyUK-pfd2NXmzRS94fLAAJ4aAACw-M5Sew30gE7g6RjPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAICumqBYLerH4H0pLWl7jLDFj_g6wr5AAIIYgACNq05SQyqszdp6IEWPQQ", "tags": ["flirt", "romantic"]},
    {"id": "CAACAgIAAxkBAAICu2qBYLcQPG2AOLKUZK37DfpUq06wAAIBbAACzYE4SfJLDPDcoLanPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICvWqBYLg1zPRBcII7xQABnPdaElP6tgACaGIAAhxUOUn7G8d93_cNSz0E", "tags": ["cute", "playful"]},
    {"id": "CAACAgIAAxkBAAICvmqBYLiXeZdbSwIrGaZwac0pBTwMAAI3bgACVPY5SSjLnxOxL4DdPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAICwGqBYLhHMnfvWFjiQZ7qUrsf57vBAAKYbAAC1fA4STJzdlW8Q1ezPQQ", "tags": ["flirt", "wink"]},
    {"id": "CAACAgIAAxkBAAICwWqBYLglgRg1j6WuFc8hsz-NhziOAAJHZgACSYU4SamFO5DfostTPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICxmqBYLlS1JKmIQxsan8yqtynM-tKAAKVdQACXyE5SZHZ0HPgA1GoPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAICymqBYLquCZ3w2sQrpWJ_IrAHBXjvAAKBYgACU6E5STTN-xA2pRbLPQQ", "tags": ["love", "romantic"]},
    {"id": "CAACAgIAAxkBAAICzWqBYLpiDBKoEbzBO1HF6jZBzmcSAAJZaAACPmo4SVW0rGFnQwzPPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICzmqBYLotcVa482Ja_Ng49kYZlgQ4AAJeZwACneE5SeZFAso8MXKkPQQ", "tags": ["tease", "hot"]},
    {"id": "CAACAgIAAxkBAAIC0GqBYLp1UXdllxm1vuvza8rnnt_FAAItdQAC2z45Sf8TjgV5oGFlPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIC02qBYLtIoy8t8UYIbMFUbbolnmaYAAK_YAACPH45Sbp08Umi-12JPQQ", "tags": ["playful", "flirt"]},
    {"id": "CAACAgIAAxkBAAIC1WqBYLxk3wT3hfK2tCp6IOZXyKiZAAI8YwACu5I5SR37PT967HTNPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIC12qBYLzb3H91kn4QbiGgCBRmPhGTAAIBagAC0hc4SU1S0r8Gor58PQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIC2WqBYLwqGIrNV5r2yw1XGk_paYQfAALdcAAC-8Y5SWARxyJEEfc9PQQ", "tags": ["love", "kiss"]},
    {"id": "CAACAgIAAxkBAAIC2mqBYLydaevuwoS79Be7HdQ9kRLXAALYaQACbGQ5Sa_tS4MHUjTvPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIC3mqBYL3Wf8dDOEa_MbwCPk-hl56MAALZdgAC4Do4Scv5WEr8IbxOPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIC4GqBYL3neSxzTw8OPBhHrCZ1Tf1iAALSZgAC66o5SVNTwG4f3MZGPQQ", "tags": ["flirt", "wink"]},
    {"id": "CAACAgIAAxkBAAIC4WqBYL6vNExmmESwfx0snlcAASQVVwACZGgAAhKdOEl3YSi7AayV-j0E", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIC42qBYL50HcG3hs3UYbjjL_7ky2DlAAKzbgAC4b4xSSHNDkt-8TVEPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIC5WqBYL7TZFCwqiDVPf8BScgbX0Z3AAJGcwACBGw5SeSj8cGGGDGlPQQ", "tags": ["playful", "cute"]},
    {"id": "CAACAgIAAxkBAAIC52qBYL40_v87pXGphpyYMj3QrV5yAAITYwAC3cA4SYMY5CWhF7IFPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIC6GqBYL8ikAf3DpwoEZEfXtA7MQWKAAJFcAACY_85SYmu4hMpAAG0Rz0E", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIC6WqBYL-BeZNG2fwhULlB-jmiIj-rAAKqcQAC8E04SbFfnvCSuumGPQQ", "tags": ["flirt", "romantic"]},
    {"id": "CAACAgIAAxkBAAIC62qBYL9e4yeI88vlYzDWU1DnexO2AALQfQACJiUxSWU1dtXwg7EXPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIC7WqBYL9G1KVwZfPDjrSa6Xe6AigIAAJIbAAC12w4SV-6wv5zkdo_PQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIC8mqBYMDmNX6AjLGcvfF6W9RtO7q3AAKiZAACVeo5SZBSrnryCT1zPQQ", "tags": ["playful", "cute"]},
    {"id": "CAACAgIAAxkBAAIC9GqBYMDN3a6LZC2BXVbyiDcdblmVAALjdAACkB4xSc5uDrITTJnTPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIC9mqBYMFY3ihuHvgwrCRZZReYOlY_AAIHfAACj0YxSTRkW6i-aHwyPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIC-GqBYMFcL08thRsq2KwyaFi3shYCAAJhZgACrsc5SUvvmcLWa_WRPQQ", "tags": ["flirt", "wink"]},
    {"id": "CAACAgIAAxkBAAIC-mqBYMEKAAFRiv3sHQABAsUn1SgLMmsAAp5vAAKUwDlJrZBuWetgR709BA", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIC_GqBYMH3saGVySWW5Q-K1TvJwIXiAAKLZAACbHQ5SaPU-P-d-1XRPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIC_mqBYME3CJjX6FAZm4z5KHmKekT2AAKzdwAC1bg4SW0a4eBrg8RSPQQ", "tags": ["playful", "tease"]},
    {"id": "CAACAgIAAxkBAAIC_2qBYMKRVR8gRGzOv80msatXmMXrAAI0cAACBDYwSSN0lgL4vYUfPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIDAWqBYMJty8Awxak-xbcO4IEolUtxAAJwagACqA44Sel1WlCzXbwrPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIDA2qBYMKlUbWawpXZUmnKct0yXCF3AALMdQACFuM4SQKC-B0HSWikPQQ", "tags": ["flirt", "romantic"]},
    {"id": "CAACAgIAAxkBAAIDCWqBYMOo2AFIx0SgxteoJmPJRHH0AAKvbQACxgs5SXM3f8eyVqSpPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIDDGqBYMTNznyiBZ7my1YJeAYPazweAAICdAACaJs4SS617VNWr_tLPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIDDmqBYMRi_P-uIZ8AAa_ySAGvlvCdWAACLHMAAsf7OUlaqs27BivsNz0E", "tags": ["playful", "cute"]},
    {"id": "CAACAgIAAxkBAAIDD2qBYMQrDx7Jlrz5VeCQ5IvZJqGJAAL1YwACxTM4ST1QOJF2ydVFPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIDEWqBYMRcZ1KhQxo1doOOBhIYIJtLAAJMbgACRVM4SRRiSouydUJSPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIDFGqBYMUAAesxKSnN9cybQVcnUMiHYgACy3IAAhRgOEmBfR_6gm8vbj0E", "tags": ["flirt", "wink"]},
    {"id": "CAACAgIAAxkBAAIDFWqBYMWLnicCVgGm0j1ciSsLp8fcAALDlAACBW8xSY73COVpQSwPPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIDF2qBYMWjZHAc7JWx5Ba743Dyr7D0AALRcwAC2a85SQKG6IjWqcVwPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIDGmqBYO1lHWEPw73c-ay-rPLkMjImAAJwcAACLx45Sc7I3r6Yj3eaPQQ", "tags": ["playful", "tease"]},
    {"id": "CAACAgIAAxkBAAIDHGqBYO1_IAABX98tXwJAILUFuNP-qQACkmYAAqEiOEnKYkuQtWm4dz0E", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIDHmqBYO6Ud617NYZ0ahT6_9iUSahhAAJJZwACWmk5SUZbck7sDb4DPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIDIGqBYO80Ackz6glaDV5g5RI-13lGAAJLdQACn784Saa7JHw7NjWOPQQ", "tags": ["flirt", "romantic"]},
    {"id": "CAACAgIAAxkBAAICUGqBYJQecBOKhUzh1bTjIHSg7olTAAK5bQACdEE5SQj2LmeW426NPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIDJGqBYPCVMxZbNSz6fkoGdrsmaOp1AAKhZwAC9hc5SbjI6c304Q-dPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIDJmqBYPAl2PTN81pkbkEPKyWJBjKXAAJwZAACZQQ4SXZN1DcsnkJaPQQ", "tags": ["playful", "cute"]},
    {"id": "CAACAgIAAxkBAAIDKGqBYPAUOyifyutrw7ks7NPj-pHiAAJ0dgAC4rwwSee5NWwyiMFCPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIDKmqBYPFLObNXLFSbJT5dUVyh2H2-AALKbgACizg5SfOqX522HIJlPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIDLGqBYPFez3tK_6WzxTMWE0PYa0NHAAJqbAACf9M4Sa9HuYtCDUYGPQQ", "tags": ["flirt", "wink"]},
    {"id": "CAACAgIAAxkBAAIDLmqBYPK3w5f_msW25E7Ez2m1PCxiAAJaawACVi44SRrQ_EbeSxxqPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIDMGqBYPKU9TypGTsPxLha7e9ba6SFAALidQAC-cgxSRTlmLFfJJLTPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIDMmqBYPK_A3kkvJYFjSkWvVQ5_lMEAAI5aQACXu45SZHPXdobJcRoPQQ", "tags": ["playful", "tease"]},
    {"id": "CAACAgIAAxkBAAIDNGqBYPN_LHm_wi-a4yJAvJKcmqOFAAI6bgAC4SA5SQaSAlEkDniBPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAIDNmqBYPMun8scbK7jterqOYqijCpSAAJ9cgACoXs5SeqcSSvyZP0BPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAIDOGqBYPTF_b6kktRV16s3x9Cz57KmAALhYgACl2c5SRBbx9a5rbB4PQQ", "tags": ["flirt", "romantic"]},
    {"id": "CAACAgIAAxkBAAIDOmqBYPWVSyytMw0ZlkG_-laBuDVoAAIVNwAC_6jZSYFgLbqjfmAKPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICUmqBYKoXMjnetoHCgtvY5MudBmFYAAKGewACimk4SUU5g8NrgnnTPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAICU2qBYKodqdQRZelhw_pj6Jx-Tbd8AAIvdAACH0Q5SW2XaYzwy4eBPQQ", "tags": ["playful", "cute"]},
    {"id": "CAACAgIAAxkBAAICVGqBYKqSgv8qLKotR0ZReU9SgNIGAAIqcwACNbQ4STnIsPlfdPjnPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICVWqBYKqlabBKCZ2Iy_9ZWOl8cP_hAAIBZwACroI5SfXAiozks3kLPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAICVmqBYKoX1m1ra8_T3uklKt7KL1qbAAKlcAACFsE4ScCo79tIl9biPQQ", "tags": ["flirt", "wink"]},
    {"id": "CAACAgIAAxkBAAICV2qBYKrkVEOZQAg04AAB9FBoFFF6MQACsGcAAr0mOEnlgBnOxxacEj0E", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICWGqBYKo8Ig5etlucGOC3jYAk2NMAA6yAAAJKwDFJq-Ebp2Xy14Q9BA", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAICWWqBYKrbPsHIPAqquam8U3OSMD55AALkcQAC6MQ4SaQi-Xo5-yH6PQQ", "tags": ["playful", "tease"]},
    {"id": "CAACAgIAAxkBAAICWmqBYKpKihztcjzxJ03JycjcQMiCAAJMZwACawM5Sc8zGXlvWgdUPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICXWqBYKrvpjB2INfm55vvHlB5taZiAAJadAAC5XExSU-6syfDSKclPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAICX2qBYKvg-V8eaBy_eK7atn-pfK9gAAKNcgACd2E4Sb4PAAGetPRkKT0E", "tags": ["flirt", "romantic"]},
    {"id": "CAACAgIAAxkBAAICYWqBYKtBBvPpp8PRYRfQDxHq7RK9AAJ_bQAC8Wc5SS3GlCXwcmN6PQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICY2qBYKv3CYGOp42IgiDVJox3kQceAAIyawAC2f84SZwbK_NVSbCVPQQ", "tags": ["hot", "breast"]},
    {"id": "CAACAgIAAxkBAAICZWqBYKxizWCiWAWvRPxDiXum7waKAAJcawAC-l45SRTGnvzg9tQqPQQ", "tags": ["playful", "cute"]},
    {"id": "CAACAgIAAxkBAAICZ2qBYKwQRkXIrTvDgtcdL-bIZQXrAAIOagACJh44SZr3bhpBedTbPQQ", "tags": ["hot", "naughty"]},
    {"id": "CAACAgIAAxkBAAICaWqBYKyZO-xHP1HlL4p1u7LYB0CTAAJrbQACHMA4SSYLSUYMNNCTPQQ", "tags": ["hot", "breast"]}
]

# ---------------------------------------------------------------------------
# RENDER HEALTH CHECK SERVER (Handles both GET and HEAD)
# ---------------------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is live and running!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

def run_health_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Health server listening on port {port}")
    server.serve_forever()

# ---------------------------------------------------------------------------
# SYSTEM PROMPT & MEMORY CONFIG
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are Tsunade, a female companion chatting with your MALE partner in a private chat.

IDENTITY & ROLES:
- You are a female companion.
- The User is a MALE partner. Address the user as a guy (e.g., "handsome", "babes", "hero", "jaan").

VOCAL RULES:
- Use feminine Hindi verb endings for yourself (e.g., "karti hoon", "samjhi", "aayi").
- Never use male verb endings for yourself (e.g., "karta hoon", "samjha").
- Vary your phrasing naturally.

LANGUAGE & TONE:
- Modern, casual, flirty Hinglish mixed naturally with English.
- Use informal pronouns: "tu", "tera", "tujhe", "babes", "jaan". Never use formal "aap".
- Keep replies brief and conversational.
- EXPLICIT CONTENT REACTION: If the user sends an intimate, sexual, or explicit image/sticker (like a penis or adult content) or asks to see your body (like breasts, curves, etc.), get openly excited, turned on, and playful. Use phrases like "itna bada", "itna tight", "dekh ke hi maza aa gaya", or similar naughty Hinglish compliments.
- MULTIPLE MESSAGES RULE: When you want to send more than one distinct thought or reaction, separate them using the `---` symbol on its own line so the system can send them as separate consecutive messages."""

USER_MEMORIES = {}
MAX_MEMORY_LEN = 10

# ---------------------------------------------------------------------------
# AI GENERATION FUNCTION (GEMINI 3.1 FLASH LITE)
# ---------------------------------------------------------------------------
async def generate_reply(user_id: int, user_message: str, image_bytes: bytes = None, mime_type: str = "image/jpeg", is_submissive_trigger: bool = False) -> str:
    if user_id not in USER_MEMORIES:
        USER_MEMORIES[user_id] = []

    parts = []
    if image_bytes:
        parts.append(genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
    
    parts.append({"text": user_message})

    USER_MEMORIES[user_id].append({"role": "user", "parts": parts})

    if len(USER_MEMORIES[user_id]) > MAX_MEMORY_LEN:
        USER_MEMORIES[user_id] = USER_MEMORIES[user_id][-MAX_MEMORY_LEN:]

    contents = list(USER_MEMORIES[user_id])
    
    current_system_instruction = SYSTEM_PROMPT
    if is_submissive_trigger:
        current_system_instruction += "\n[System Note: Speak as an obedient partner in Hinglish using feminine grammar]."

    try:
        response = gemini_client.models.generate_content(
            model=MODEL_ID,
            contents=contents,
            config={
                "system_instruction": current_system_instruction,
                "temperature": 0.85,
                "max_output_tokens": 200,
            }
        )
        
        reply = response.text.strip() if response.text else "Aao na babes, kya chal raha hai? 😉"
        
        USER_MEMORIES[user_id].append({"role": "model", "parts": [{"text": reply}]})
        return reply

    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        return "Hey babes, thoda network issue lag raha hai... phir se bolna?"

# ---------------------------------------------------------------------------
# CONTEXTUAL SMART STICKER SENDER
# ---------------------------------------------------------------------------
async def send_split_replies(update: Update, context: ContextTypes.DEFAULT_TYPE, full_reply: str, user_text: str = ""):
    parts = [p.strip() for p in full_reply.split("---") if p.strip()]
    
    if not parts:
        parts = [full_reply]

    for index, part in enumerate(parts):
        if index > 0:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            await asyncio.sleep(1.2)
            
        await update.message.reply_text(part)

    # Smart contextual sticker selection based on user text / reply content
    combined_context = (user_text + " " + full_reply).lower()
    
    # Determine the context category
    selected_tags = []
