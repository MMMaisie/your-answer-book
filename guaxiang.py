from flask import Flask, request, render_template_string, redirect, url_for, abort, jsonify
from datetime import datetime
import hashlib
import sqlite3
import json
import re
import os
from urllib.parse import quote_plus

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import stripe
except ImportError:
    stripe = None

app = Flask(__name__)
DB_NAME = "readings.db"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_ENABLE_ALIPAY = os.getenv("STRIPE_ENABLE_ALIPAY", "0") == "1"
ALIPAY_PAYMENT_URL = os.getenv("ALIPAY_PAYMENT_URL", "")
WECHAT_PAYMENT_URL = os.getenv("WECHAT_PAYMENT_URL", "")
ALIPAY_QR_URL = os.getenv("ALIPAY_QR_URL", "")
WECHAT_QR_URL = os.getenv("WECHAT_QR_URL", "")

if stripe is not None and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

TEXTS = {
    "zh": {
        "title": "你的答案之书",
        "subtitle": "掷下硬币，看清现在的“势”。一卦一问。",
        "guide_title": "开始之前",
        "guide_text": "先不要急着提问。\n\n把注意力放在你真正放不下的事情上。\n\n准备3枚相同的硬币，或任意3个能区分正反面的物件。\n\n连续掷6次。每一次，选择有几个“数字面 / 正面”朝上。\n\n不要反复问同一个问题，第一卦，往往最接近你当下真正的直觉。",
        "question": "你的问题",
        "question_ph": "例如：我能不能在3个月内拿到offer？我和这个人适不适合继续？我能否拿下这个项目？",
        "time": "此刻",
        "time_ph": "默认使用现在时间，也可以修改",
        "time_hint": "例如：2026年5月17日下午9点 → 2026 / 05 / 17 / 21",
        "coin_title": "六次落下的结果",
        "coin_hint": "在它们落下之前，先想清你真正想问的事。按照顺序选择每次有几个“数字面 / 正面”朝上。",
        "yao": "第{n}次",
        "submit": "看看这一卦",
        "select": "选择",
        "report": "答案浮现",
        "asked": "你问的是",
        "time_result": "起卦时间",
        "full_title": "完整解析",
        "full_hint": "完整版会展开：当前局势、真正阻力、未来变化与下一步建议。",
        "full_btn": "查看完整解析",
    },
    "en": {
        "title": "The Book of Answers",
        "subtitle": "Ask once. Let the hexagram reveal what the moment is trying to tell you.",
        "guide_title": "Before You Cast",
        "guide_text": "Before you ask, pause for a moment.\n\nHold one question in your mind — not a vague wish, but the decision you truly need clarity on.\n\nCast the six lines yourself, or let the system cast them for you.\n\nThe hexagram reflects the pattern around this question now.\n\nAsk once. The first cast is usually the clearest.",
        "question": "Your Question",
        "question_ph": "Examples: Will I receive the offer? Should I leave this relationship? Is now the right time to move? What is blocking my progress?",
        "time": "The Moment",
        "time_ph": "Use the current moment, or adjust the time of your cast.",
        "time_hint": "Example: 9PM on May 17, 2026 → 2026 / 05 / 17 / 21",
        "coin_title": "Cast the Six Lines",
        "coin_hint": "Hold your question clearly. Each throw becomes one line of the hexagram.",
        "yao": "Throw {n}",
        "submit": "Reveal the Reading",
        "select": "Select",
        "report": "Your Reading Reveals",
        "asked": "Your question",
        "time_result": "Cast at",
        "full_title": "The Full Reading",
        "full_hint": "The full reading reveals what sits beneath the first answer: hidden influence, timing, resistance, and the action the hexagram points toward.",
        "full_btn": "Reveal the Full Reading",
    }
}

HTML = """
<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ t['title'] }}</title>

<style>
:root{
    --gold:#d4af37;
    --gold2:#f5d48a;
    --text:#f3e7c9;
    --muted:#a8926f;
    --font-body:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Noto Sans SC","Segoe UI",Arial,sans-serif;
    --font-title:"Noto Serif SC","Source Han Serif SC","Songti SC","STSong","KaiTi",serif;
}

*{ box-sizing:border-box; }

body{
    margin:0;
    background:
        radial-gradient(circle at 50% -10%, rgba(214,173,79,.20) 0, rgba(214,173,79,.06) 32%, transparent 56%),
        linear-gradient(180deg, #100b07 0%, #090807 55%, #050505 100%);
    color:var(--text);
    font-family:var(--font-body);
    font-size:16px;
    line-height:1.65;
}

.container{
    max-width:860px;
    margin:auto;
    padding:46px 22px 80px;
}

.title{
    text-align:center;
    margin-bottom:34px;
}

.title h1{
    font-family:var(--font-title);
    font-size:clamp(34px,7vw,52px);
    line-height:1.12;
    color:var(--gold);
    margin:0;
    font-weight:600;
    letter-spacing:.08em;
}

.subtitle{
    margin-top:12px;
    color:#d8c6a1;
    font-size:15px;
    opacity:.86;
    letter-spacing:.04em;
}

.lang-select{
    position:fixed;
    top:16px;
    right:18px;
    z-index:999;
    display:flex;
    align-items:center;
    gap:6px;
    color:#bca98a;
    font-size:12px;
    font-style:normal;
}

.lang-select select{
    width:92px !important;
    height:30px;
    padding:4px 8px;
    border-radius:999px;
    font-size:12px;
    font-family:var(--font-body);
    font-style:normal;
}

.guide-box{
    margin-bottom:28px;
    padding:18px 18px 18px 16px;
    border-left:1px solid rgba(212,175,55,.42);
    background:linear-gradient(90deg, rgba(212,175,55,.055), rgba(255,255,255,0));
    border-radius:0 18px 18px 0;
}

.guide-title,
label,
.coin-card h3{
    font-family:var(--font-title);
    color:var(--gold2);
    font-weight:700;
    font-style:normal;
    letter-spacing:.03em;
}

.guide-title{
    font-size:22px;
    margin-bottom:12px;
}

.manual-note{
    display:block;
    margin-top:6px;
    color:#bca98a;
    font-size:13.5px;
    line-height:1.8;
    font-style:italic;
    opacity:.78;
}

.guide-text,
.question-example,
.time-tip,
.coin-mini-tip{
    color:#bca98a;
    font-size:13.5px;
    line-height:1.8;
    font-style:italic;
    opacity:.78;
    white-space:pre-line;
}
.guide-text{
    max-width:720px;
}

label{
    display:block;
    margin:22px 0 10px;
    font-size:22px;
    line-height:1.35;
}

textarea,
input,
select{
    width:100%;
    background:#060606;
    border:1px solid rgba(212,175,55,.42);
    border-radius:16px;
    color:white;
    padding:14px 16px;
    font-size:16px;
    font-family:var(--font-body);
    font-style:normal;
    outline:none;
}

textarea{
    min-height:72px;
    height:72px;
    resize:none;
    line-height:1.5;
    padding:14px 18px;
    overflow:hidden;
}

textarea::placeholder,
input::placeholder{
    color:#8f7b5f;
    font-style:italic;
    font-size:14px;
    line-height:1.8;
    opacity:.72;
}

.time-inline{
    display:flex;
    align-items:center;
    gap:10px;
    flex-wrap:wrap;
    margin-top:12px;
}

.time-inline input{
    width:88px;
    height:52px;
    text-align:center;
    font-size:18px;
    font-weight:700;
    border-radius:14px;
    padding:8px 10px;
}

.time-inline span{
    color:var(--gold2);
    font-size:18px;
    font-family:var(--font-title);
}

.coin-mini-tip{
    max-width:680px;
}

.coin-grid{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:14px;
}

.coin-card{
    background:rgba(255,255,255,.02);
    border:1px solid rgba(212,175,55,.18);
    border-radius:18px;
    padding:14px;
}

.coin-card h3{
    margin:0 0 10px;
    font-size:16px;
}

.coin-card select{
    height:50px;
    padding:10px 14px;
}

button{
    width:100%;
    margin-top:30px;
    border:none;
    border-radius:999px;
    padding:17px 22px;
    background:linear-gradient(90deg,#8d5d17,#e1b85b,#8d5d17);
    color:black;
    font-size:20px;
    font-weight:800;
    cursor:pointer;
    letter-spacing:.04em;
}

.cast-mode{
    display:flex;
    gap:12px;
    margin:20px 0 18px;
}

.mode-btn{
    margin:0;
    padding:13px 16px;
    border-radius:999px;
    border:1px solid rgba(212,175,55,.22);
    background:rgba(255,255,255,.03);
    color:#d8c6a1;
    font-size:15px;
    font-weight:600;
    letter-spacing:.03em;
    transition:.25s;
}

.mode-btn.active{
    background:linear-gradient(90deg,#8d5d17,#e1b85b,#8d5d17);
    color:#050505;
}

.auto-modal{
    display:none;
    position:fixed;
    inset:0;
    z-index:2000;
    background:rgba(0,0,0,.72);
    backdrop-filter:blur(8px);
    align-items:center;
    justify-content:center;
    padding:20px;
}

.auto-modal.show{
    display:flex;
}

.auto-box{
    width:min(420px, 92vw);
    background:linear-gradient(180deg,#17110d,#060606);
    border:1px solid rgba(212,175,55,.38);
    border-radius:24px;
    padding:24px;
    text-align:center;
    box-shadow:0 24px 80px rgba(0,0,0,.6);
}

.auto-box h3{
    margin:0 0 12px;
    color:var(--gold2);
    font-family:var(--font-title);
    font-size:24px;
}

.auto-box p{
    color:#bca98a;
    font-size:14px;
    line-height:1.8;
    font-style:italic;
}

.auto-coins{
    color:var(--gold2);
    font-size:38px;
    letter-spacing:10px;
    margin:18px 0;
    animation:floatCoin .7s infinite alternate;
}

.auto-results{
    text-align:left;
    color:#e8d8b7;
    font-size:15px;
    line-height:1.9;
    margin:12px 0;
    min-height:130px;
}

.pay-note{
    margin:8px auto 18px;
    max-width:360px;
    color:#bca98a !important;
    font-size:14px !important;
    line-height:1.85 !important;
    font-style:italic;
}

.unlock-list{
    margin:22px auto 34px;
    text-align:left;
    max-width:360px;
}

.unlock-list div{
    margin:10px 0;
    font-size:17px;
    line-height:1.7;
    color:#e8d8b7;
}

.pay-actions{
    display:flex;
    flex-direction:column;
    gap:16px;
    margin-top:18px;
}

.pay-actions button{
    margin-top:0;
    height:72px;
    padding:0 22px;
    display:flex;
    align-items:center;
    justify-content:center;
}

.save-tip{
    margin:0 0 20px;
    padding:14px 16px;
    border:1px solid rgba(212,175,55,.18);
    border-radius:16px;
    background:rgba(212,175,55,.055);
    color:#bca98a !important;
    font-size:14px;
    line-height:1.8;
    font-style:italic;
    white-space:pre-line;
}

.loading-modal{
    display:none;
    position:fixed;
    inset:0;
    z-index:3000;
    background:rgba(0,0,0,.78);
    backdrop-filter:blur(10px);
    align-items:center;
    justify-content:center;
    padding:20px;
}

.loading-modal.show{
    display:flex;
}

.loading-box{
    width:min(430px, 92vw);
    min-height:280px;
    background:linear-gradient(180deg,#17110d,#060606);
    border:1px solid rgba(212,175,55,.42);
    border-radius:28px;
    padding:34px 26px;
    text-align:center;
    box-shadow:0 28px 90px rgba(0,0,0,.72);
}

.loading-symbol{
    width:70px;
    height:70px;
    margin:0 auto 18px;
    border-radius:50%;
    border:1px solid rgba(212,175,55,.45);
    display:flex;
    align-items:center;
    justify-content:center;
    color:var(--gold2);
    font-size:34px;
    animation:loadingSpin 2.8s linear infinite;
}

.loading-box h3{
    margin:0 0 12px;
    color:var(--gold2);
    font-family:var(--font-title);
    font-size:26px;
    letter-spacing:.05em;
}

.loading-box p{
    margin:0 auto;
    max-width:330px;
    color:#bca98a;
    font-size:14px;
    line-height:1.9;
    font-style:italic;
}

.loading-dots{
    display:flex;
    justify-content:center;
    gap:8px;
    margin-top:24px;
}

.loading-dots span{
    width:8px;
    height:8px;
    border-radius:50%;
    background:var(--gold2);
    opacity:.35;
    animation:loadingPulse 1.2s infinite ease-in-out;
}

.loading-dots span:nth-child(2){ animation-delay:.2s; }
.loading-dots span:nth-child(3){ animation-delay:.4s; }

@keyframes loadingSpin{
    from{ transform:rotate(0deg); }
    to{ transform:rotate(360deg); }
}

@keyframes loadingPulse{
    0%, 80%, 100%{ opacity:.25; transform:translateY(0); }
    40%{ opacity:1; transform:translateY(-6px); }
}

@keyframes floatCoin{
    from{ transform:translateY(0); opacity:.65; }
    to{ transform:translateY(-6px); opacity:1; }
}

.result{
    margin-top:40px;
    scroll-margin-top:24px;
    background:rgba(255,255,255,.03);
    border:1px solid rgba(212,175,55,.2);
    border-radius:24px;
    padding:26px;
}

.result h2,
.result h3{
    color:#ffd57a;
    font-family:var(--font-title);
}

.result p{
    line-height:1.9;
    color:#e8d8b7;
    white-space:pre-line;
    margin:0 0 18px;
}

.result strong{
    color:#f5d48a;
}

.reading-text{
    white-space:pre-line;
    line-height:2.05;
    color:#e8d8b7;
    font-size:17px;
}

.free-reading{
    margin-top:22px;
}

.paid-reading{
    margin-top:26px;
    padding-top:4px;
}

.paid-reading::first-line{
    color:#ffd57a;
}

.full-box{
    margin-top:28px;
    padding-top:20px;
    border-top:1px solid rgba(212,175,55,.25);
}

.full-hint{
    color:#bca98a !important;
    font-style:italic;
}

#paidBox{
    display:none;
    margin-top:24px;
}


.share-actions{
    display:flex;
    gap:12px;
    margin-top:24px;
    flex-wrap:wrap;
}

.share-card-btn,
.copy-link-btn{
    flex:1 1 220px;
    display:flex;
    align-items:center;
    justify-content:center;
    text-decoration:none;
    min-height:58px;
    border-radius:999px;
    font-size:17px;
    font-weight:800;
    letter-spacing:.03em;
}

.share-card-btn{
    background:linear-gradient(90deg,#8d5d17,#e1b85b,#8d5d17);
    color:#050505;
}

.copy-link-btn{
    margin-top:0;
    background:rgba(255,255,255,.03);
    color:#e8d8b7;
    border:1px solid rgba(212,175,55,.28);
}

.manual-pay-grid{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:14px;
    margin:18px 0 8px;
}

.manual-pay-card{
    border:1px solid rgba(212,175,55,.22);
    border-radius:18px;
    padding:14px;
    background:rgba(255,255,255,.025);
    text-align:center;
}

.manual-pay-card h4{
    margin:0 0 10px;
    color:#f5d48a;
    font-size:16px;
}

.manual-pay-card img{
    width:150px;
    height:150px;
    object-fit:contain;
    border-radius:12px;
    background:#fff;
    padding:8px;
    display:block;
    margin:8px auto 12px;
}

.manual-pay-card a{
    display:block;
    color:#f5d48a;
    text-decoration:none;
    font-weight:700;
    margin-top:8px;
}

.pay-divider{
    margin:18px 0 10px;
    color:#8f7b5f;
    font-size:13px;
    text-align:center;
}

.pay-small-note{
    color:#bca98a !important;
    font-size:13px !important;
    line-height:1.75 !important;
    margin:10px 0 0 !important;
}

.stripe-pay-btn{
    margin-top:0;
}

.manual-unlock-btn{
    background:rgba(255,255,255,.03) !important;
    color:#e8d8b7 !important;
    border:1px solid rgba(212,175,55,.28) !important;
}

@media(max-width:560px){
    .manual-pay-grid{
        grid-template-columns:1fr;
    }
}

@media(max-width:700px){
    .container{ padding:42px 18px 64px; }
    .coin-grid{ grid-template-columns:1fr 1fr; gap:10px; }
    label{ font-size:20px; margin-top:20px; }

    .guide-box{
        padding:16px 14px;
        margin-bottom:24px;
    }

    .time-inline{
        gap:7px;
    }

    .time-inline input{
        width:68px;
        height:48px;
        font-size:16px;
        padding:8px 6px;
    }

    .time-inline span{
        font-size:15px;
    }

    .coin-card{ padding:12px; }

    .cast-mode{
        gap:10px;
    }

    .mode-btn{
        font-size:14px;
        padding:12px 10px;
    }
}
</style>
</head>

<body>

<div class="container">

    <form method="POST" id="mainForm">
        <input type="hidden" name="submit_action" id="submitAction" value="">

        <div class="lang-select">
            <span>{{ '语言' if lang == 'zh' else 'Language' }}:</span>
            <select name="lang" onchange="window.isLangSwitch=true; document.getElementById('submitAction').value='language'; this.form.submit()">
                <option value="zh" {% if lang=='zh' %}selected{% endif %}>中文</option>
                <option value="en" {% if lang=='en' %}selected{% endif %}>English</option>
            </select>
        </div>

        <div class="title">
            <h1>{{ t['title'] }}</h1>
            <div class="subtitle">{{ t['subtitle'] }}</div>
        </div>

        <div class="guide-box">
            <div class="guide-title">{{ t['guide_title'] }}</div>
            <div class="guide-text">{{ t['guide_text'] }}</div>
        </div>

        <label>{{ t['question'] }}</label>
        <textarea name="question" placeholder="{{ t['question_ph'] }}" required></textarea>

        <label>{{ t['time'] }}</label>
        <div class="time-tip">{{ t['time_ph'] }}</div>

        <div class="time-inline">
            <input name="year" value="{{ current_year }}" maxlength="4">
            <span>{{ "年" if lang=="zh" else "Y" }}</span>

            <input name="month" value="{{ current_month }}" maxlength="2">
            <span>{{ "月" if lang=="zh" else "M" }}</span>

            <input name="day" value="{{ current_day }}" maxlength="2">
            <span>{{ "日" if lang=="zh" else "D" }}</span>

            <input name="hour" value="{{ current_hour }}" maxlength="2">
            <span>{{ "时" if lang=="zh" else "H" }}</span>
        </div>

        <div class="time-tip">{{ t['time_hint'] }}</div>

        <label>{{ t['coin_title'] }}</label>

       <div class="coin-mini-tip">
        {{ t['coin_hint'] }}
        <span class="manual-note">
            {{ "当然，自己亲手掷出的这一卦，往往更接近答案。" if lang=="zh" else "A hand-cast reading often carries the clearest intention." }}
        </span>
        </div>
        <div class="cast-mode">
            <button type="button" class="mode-btn active" id="manualBtn" onclick="setManual()">
                {{ "我自己来" if lang=="zh" else "Cast Manually" }}
            </button>

            <button type="button" class="mode-btn" id="autoBtn" onclick="autoCast()">
                {{ "交给系统" if lang=="zh" else "Auto Cast" }}
            </button>
        </div>


        <div id="loadingModal" class="loading-modal">
            <div class="loading-box">
                <div class="loading-symbol">☯</div>
                <h3>{{ "吕主正在推演此卦" if lang=="zh" else "The hexagram is forming" }}</h3>
                <p>
                    {{ "本卦、变卦与动爻正在显化。请稍候片刻，不要关闭页面。" if lang=="zh" else "The lines are settling into place. Please keep this page open." }}
                </p>
                <div class="loading-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>

        <div id="autoModal" class="auto-modal">
            <div class="auto-box">
                <h3>{{ "交给系统" if lang=="zh" else "Auto Cast" }}</h3>
                <p id="autoMessage">
                    {{ "在开始之前，请心中默念真正想问的事。" if lang=="zh" else "Before the cast, hold your question clearly in mind." }}
                </p>

                <div class="auto-coins">◐ ◑ ◒</div>
                <div id="autoResults" class="auto-results"></div>

                <button type="button" id="confirmAutoBtn" onclick="startAutoCast()">
                    {{ "我准备好了" if lang=="zh" else "Begin the Cast" }}
                </button>
            </div>
        </div>

        <div class="coin-grid">
            {% for i in range(1,7) %}
            <div class="coin-card">
                <h3>{{ t['yao'].replace('{n}', i|string) }}</h3>
                <select name="word{{i}}" required>
                    <option value="">{{ t['select'] }}</option>
                    <option value="0">0</option>
                    <option value="1">1</option>
                    <option value="2">2</option>
                    <option value="3">3</option>
                </select>
            </div>
            {% endfor %}
        </div>

        <button type="submit" id="castSubmitBtn" onclick="document.getElementById('submitAction').value='cast'">{{ t['submit'] }}</button>

    </form>

    {% if result %}
    <div class="result" id="resultBox">
        <h2>{{ t['report'] }}</h2>
        <p><strong>{{ t['asked'] }}：</strong>{{ question }}</p>
        <p><strong>{{ t['time_result'] }}：</strong>{{ cast_time }}</p>
        <div class="reading-text free-reading">{{ result }}</div>

        {% if share_url %}
        <div class="share-actions">
            <a class="share-card-btn" href="{{ share_url }}">
                {{ "生成分享卡片" if lang=="zh" else "Share Result" }}
            </a>
            <button type="button" class="copy-link-btn" onclick="copyReadingLink()">
                {{ "复制本卦链接" if lang=="zh" else "Copy Reading Link" }}
            </button>
        </div>
        {% endif %}

        <div class="full-box">
            <h3>{{ t['full_title'] }}</h3>

            {% if paid_unlocked %}
                <p class="save-tip">
                    {{ "已解锁完整解析。建议截图保存，也可以复制本卦链接稍后查看。" if lang=="zh" else "Complete reading unlocked. Save this page or copy the link to return later." }}
                </p>
            {% else %}
                <p class="full-hint">{{ t['full_hint'] }}</p>
                <button type="button" onclick="openPayModal()">
                    {{ t['full_btn'] }}
                </button>
            {% endif %}

            <div id="paidBox" style="display:{{ 'block' if paid_unlocked else 'none' }};">
                <p class="save-tip">
                    {{ "提示：完整解析解锁后，请截图保存，也可以复制本卦链接。" if lang=="zh" else "Tip: Save this page or copy the link after unlocking." }}
                </p>
                <div class="reading-text paid-reading">
                    {{ paid_result|safe }}
                </div>
            </div>
        </div>
    </div>
    {% endif %}

</div>

<script>
const pageLang = "{{ lang }}";
const isResultPage = "{{ '1' if result else '0' }}";

window.addEventListener("load", function(){
    if(isResultPage === "1"){
        const box = document.getElementById("resultBox");
        if(box){
            setTimeout(function(){
                box.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });
            }, 300);
        }
    }
});

function notice(zh, en){
    alert(pageLang === "zh" ? zh : en);
}

function copyReadingLink(){
    const link = window.location.href;
    if(navigator.clipboard && navigator.clipboard.writeText){
        navigator.clipboard.writeText(link).then(function(){
            notice("本卦链接已复制。", "Reading link copied.");
        }).catch(function(){
            prompt(pageLang === "zh" ? "复制这个链接：" : "Copy this link:", link);
        });
    }else{
        prompt(pageLang === "zh" ? "复制这个链接：" : "Copy this link:", link);
    }
}

function setManual(){
    if(!validateBeforeCast()){
        return;
    }

    document.getElementById("manualBtn").classList.add("active");
    document.getElementById("autoBtn").classList.remove("active");
}

function validateBeforeCast(){
    const question = document.querySelector('textarea[name="question"]').value.trim();
    const year = document.querySelector('input[name="year"]').value.trim();
    const month = document.querySelector('input[name="month"]').value.trim();
    const day = document.querySelector('input[name="day"]').value.trim();
    const hour = document.querySelector('input[name="hour"]').value.trim();

    if(question === ""){
        notice("请先写下你真正想问的问题。", "Please write your question first.");
        document.querySelector('textarea[name="question"]').focus();
        return false;
    }

    if(year === "" || month === "" || day === "" || hour === ""){
        notice("请先确认起卦时间。", "Please confirm the casting time first.");
        return false;
    }

    return true;
}

function autoCast(){
    if(!validateBeforeCast()){
        return;
    }

    document.getElementById("autoBtn").classList.add("active");
    document.getElementById("manualBtn").classList.remove("active");

    document.getElementById("autoModal").classList.add("show");
    document.getElementById("autoResults").innerHTML = "";
    document.getElementById("confirmAutoBtn").style.display = "block";

    document.getElementById("autoMessage").innerText =
        pageLang === "zh"
        ? "在开始之前，请闭眼几秒，想清你真正想问的事。"
        : "Before we begin, close your eyes for a few seconds and hold your true question clearly in mind.";
}

function startAutoCast(){
    const btn = document.getElementById("confirmAutoBtn");
    const msg = document.getElementById("autoMessage");
    const results = document.getElementById("autoResults");

    btn.style.display = "none";
    results.innerHTML = "";

    msg.innerText =
        pageLang === "zh"
        ? "系统正在为你起这一卦。"
        : "The system is casting the six lines.";

    let i = 1;

    const timer = setInterval(() => {
        const value = Math.floor(Math.random() * 4);

        document.querySelector(`[name="word${i}"]`).value = value;

        results.innerHTML +=
            pageLang === "zh"
            ? `第${i}次：${value} 个数字面 / 正面朝上<br>`
            : `Throw ${i}: ${value} number/front side(s) facing upward<br>`;

        i++;

        if(i > 6){
            clearInterval(timer);

            msg.innerText =
                pageLang === "zh"
                ? "六次已完成。结果已经填入页面。"
                : "The six lines are complete. Your cast is ready.";

            setTimeout(() => {
                document.getElementById("autoModal").classList.remove("show");
            }, 1500);
        }
    }, 850);
}

document.querySelectorAll('select[name^="word"]').forEach((el) => {
    el.addEventListener("focus", function(){
        if(!validateBeforeCast()){
            this.blur();
        }
    });

    el.addEventListener("change", function(){
        if(!validateBeforeCast()){
            this.value = "";
        }
    });
});


function showLoading(){
    const modal = document.getElementById("loadingModal");
    const btn = document.getElementById("castSubmitBtn");

    if(modal){
        modal.classList.add("show");
    }

    if(btn){
        btn.disabled = true;
        btn.style.opacity = ".72";
        btn.style.cursor = "not-allowed";
        btn.innerText = pageLang === "zh" ? "吕主推演中..." : "Revealing...";
    }
}

document.getElementById("mainForm").addEventListener("submit", function(e){
    if(window.isLangSwitch){
        return;
    }

    if(!validateBeforeCast()){
        e.preventDefault();
        return;
    }

    for(let i = 1; i <= 6; i++){
        const v = document.querySelector(`[name="word${i}"]`).value;

        if(v === ""){
            e.preventDefault();
            notice("请先完成六次结果，再看这一卦。", "Please complete all six results before reading this cast.");
            return;
        }
    }

    showLoading();
});
function openPayModal(){
    document.getElementById("payModal").classList.add("show");
}

function closePayModal(){
    document.getElementById("payModal").classList.remove("show");
}

function unlockPaidReading(){
    notice(
        "如果你使用支付宝备用入口付款，请截图保存付款记录。备用入口不会自动核验；自动解锁请使用银行卡 / Alipay 支付。",
        "If you use the backup Alipay option, please keep a payment screenshot. Backup Alipay is not automatically verified; use card / Alipay checkout for automatic unlock."
    );
}
</script>
<div id="payModal" class="auto-modal">
    <div class="auto-box">
        <h3>{{ "解锁完整解读" if lang=="zh" else "Reveal the Complete Reading" }}</h3>

        <p class="pay-note">
             {{ "完整版将揭示：" if lang=="zh" else "Your complete reading reveals:" }}
        </p>

        <div class="unlock-list">
            <div>• {{ "本卦与变卦真正指向" if lang=="zh" else "The deeper meaning of the hexagram" }}</div>
            <div>• {{ "关键人物是谁" if lang=="zh" else "Hidden influences affecting the outcome" }}</div>
            <div>• {{ "真正阻力在哪里" if lang=="zh" else "The real obstacle beneath the surface" }}</div>
            <div>• {{ "未来时间窗口" if lang=="zh" else "Timing and future developments" }}</div>
            <div>• {{ "最优行动建议" if lang=="zh" else "Practical guidance for your next step" }}</div>
        </div>

        <div class="pay-actions">
            {% if stripe_enabled and seed_key %}
            <form method="POST" action="{{ url_for('create_checkout_session', seed_key=seed_key) }}">
                <button type="submit" class="stripe-pay-btn">
                    {{ "银行卡 / 支付宝 支付 AU$1.99" if lang=="zh" else "Reveal the Full Reading — AU$1.99" }}
                </button>
            </form>
            <p class="pay-small-note">
                {{ "支持银行卡；支付宝通过 Stripe Checkout 预留，审核启用后可自动跳转并自动解锁。" if lang=="zh" else "Secure checkout by Stripe. Card, Apple Pay and Google Pay are available now. Alipay will appear automatically after Stripe approval." }}
            </p>
            {% else %}
            <p class="pay-small-note">
                {{ "本地测试未检测到 Stripe 密钥或价格 ID，所以不会显示支付按钮。部署到 Render 后，只要 STRIPE_SECRET_KEY 和 STRIPE_PRICE_ID 已配置，支付按钮会自动出现。" if lang=="zh" else "Payment is hidden in this local test because Stripe keys or Price ID are not configured. On Render, the payment button appears automatically when STRIPE_SECRET_KEY and STRIPE_PRICE_ID are set." }}
            </p>
            {% endif %}

            {% if alipay_payment_url or alipay_qr_url %}
            <div class="pay-divider">
                {{ "支付宝备用入口" if lang=="zh" else "Alipay backup" }}
            </div>
            <div class="manual-pay-grid" style="grid-template-columns:1fr;">
                <div class="manual-pay-card">
                    <h4>{{ "支付宝" if lang=="zh" else "Alipay" }}</h4>
                    {% if alipay_qr_url %}
                        <img src="{{ alipay_qr_url }}" alt="Alipay QR">
                    {% endif %}
                    {% if alipay_payment_url %}
                        <a href="{{ alipay_payment_url }}" target="_blank">{{ "打开支付宝支付链接" if lang=="zh" else "Open Alipay payment link" }}</a>
                    {% endif %}
                    <p class="pay-small-note">{{ "备用支付宝入口不会自动核验；自动解锁请使用上方 Stripe Checkout。" if lang=="zh" else "Backup Alipay is not automatically verified. For automatic unlock, use Stripe Checkout above." }}</p>
                </div>
            </div>
            {% endif %}

            <button type="button" class="mode-btn" onclick="closePayModal()">
                {{ "先不看" if lang=="zh" else "Not Now" }}
            </button>
        </div>
        </div>
    </div>
</div>
</body>
</html>
"""

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            seed_key TEXT PRIMARY KEY,
            lang TEXT,
            question TEXT,
            cast_time TEXT,
            words TEXT,
            topic TEXT,
            emotion_level TEXT,
            free_text TEXT,
            paid_text TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seed_key TEXT NOT NULL,
            stripe_session_id TEXT,
            status TEXT NOT NULL DEFAULT 'paid',
            amount_total INTEGER,
            currency TEXT,
            created_at TEXT,
            paid_at TEXT
        )
    """)

    # Database migration for older local/Render databases.
    # CREATE TABLE IF NOT EXISTS will not add new columns to an existing table,
    # so we add any missing columns explicitly.
    cur.execute("PRAGMA table_info(payments)")
    existing_cols = {row[1] for row in cur.fetchall()}
    required_cols = {
        "seed_key": "TEXT",
        "stripe_session_id": "TEXT",
        "status": "TEXT DEFAULT 'paid'",
        "amount_total": "INTEGER",
        "currency": "TEXT",
        "created_at": "TEXT",
        "paid_at": "TEXT",
    }
    for col, col_type in required_cols.items():
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE payments ADD COLUMN {col} {col_type}")

    # Make paid lookup and duplicate Stripe callbacks stable.
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_seed_key ON payments(seed_key)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_stripe_session ON payments(stripe_session_id)")

    conn.commit()
    conn.close()


# Ensure database exists under gunicorn / Render too
init_db()


def stable_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def detect_topic(question):
    q = question.lower()

    love_words = [
        "感情", "喜欢", "爱", "复合", "分手", "结婚", "离婚", "暧昧",
        "对象", "男朋友", "女朋友", "前任", "他", "她", "关系", "继续",
        "relationship", "love", "marry", "break up", "ex", "continue", "holding onto"
    ]

    career_words = [
        "工作", "offer", "面试", "岗位", "升职", "跳槽", "老板", "项目",
        "拿下", "争取", "转正", "机会", "career", "job", "interview",
        "promotion", "role", "project", "secure"
    ]

    money_words = [
        "钱", "投资", "股票", "收入", "亏", "赚", "财", "成本", "生意",
        "money", "stock", "invest", "income", "profit", "business"
    ]

    legal_words = [
        "官司", "诉讼", "律师", "法院", "纠纷", "打赢", "赔偿",
        "legal", "court", "lawyer", "case", "lawsuit"
    ]

    if any(w in q for w in love_words):
        return "love"
    if any(w in q for w in career_words):
        return "career"
    if any(w in q for w in money_words):
        return "money"
    if any(w in q for w in legal_words):
        return "legal"

    return "general"
def detect_emotion_level(question, hour):
    q = question.lower()
    high_words = ["怎么办", "还会", "到底", "能不能", "会不会", "焦虑", "害怕", "崩溃", "放不下", "等", "should i", "will he", "will she", "anxious", "afraid", "can't let go"]

    try:
        h = int(hour)
    except:
        h = 12

    if any(w in q for w in high_words) or h >= 22 or h <= 4:
        return "high"
    return "normal"


def topic_label(topic, lang):
    labels = {
        "zh": {
            "love": "情感关系",
            "career": "事业工作",
            "money": "金钱资源",
            "legal": "争议官司",
            "general": "人生选择",
        },
        "en": {
            "love": "love and relationship",
            "career": "career and work",
            "money": "money and resources",
            "legal": "legal conflict",
            "general": "life decision",
        }
    }
    return labels.get(lang, labels["zh"]).get(topic, topic)
TRIGRAMS = {
    (1, 1, 1): {"name": "乾", "style": "刚健、主动、开创、需要争取"},
    (0, 0, 0): {"name": "坤", "style": "承接、等待、顺势、不可急推"},
    (0, 1, 0): {"name": "坎", "style": "阻力、风险、反复、暗处有险"},
    (1, 0, 1): {"name": "离", "style": "显露、看清、判断、真相浮现"},
    (1, 0, 0): {"name": "震", "style": "启动、惊动、变化、突然转折"},
    (0, 0, 1): {"name": "艮", "style": "停止、克制、边界、暂缓行动"},
    (0, 1, 1): {"name": "巽", "style": "渗透、沟通、慢慢推进、暗中变化"},
    (1, 1, 0): {"name": "兑", "style": "表达、关系、交换、表面和气下有真实诉求"},
}

def word_to_yao(word_count):
    word_count = int(word_count)

    if word_count == 0:
        return {"line": 1, "moving": True, "name": "老阳"}
    if word_count == 1:
        return {"line": 0, "moving": False, "name": "少阴"}
    if word_count == 2:
        return {"line": 1, "moving": False, "name": "少阳"}
    if word_count == 3:
        return {"line": 0, "moving": True, "name": "老阴"}

    return {"line": 0, "moving": False, "name": "未知"}

def build_hexagram(words):
    yaos = [word_to_yao(w) for w in words]

    original_lines = [y["line"] for y in yaos]
    changed_lines = []

    moving_positions = []

    for idx, y in enumerate(yaos, start=1):
        if y["moving"]:
            moving_positions.append(idx)
            changed_lines.append(1 - y["line"])
        else:
            changed_lines.append(y["line"])

    lower = tuple(original_lines[:3])
    upper = tuple(original_lines[3:])

    changed_lower = tuple(changed_lines[:3])
    changed_upper = tuple(changed_lines[3:])

    upper_info = TRIGRAMS.get(upper, {"name": "未知", "style": "局势不明"})
    lower_info = TRIGRAMS.get(lower, {"name": "未知", "style": "根基不明"})
    changed_upper_info = TRIGRAMS.get(changed_upper, {"name": "未知", "style": "变化不明"})
    changed_lower_info = TRIGRAMS.get(changed_lower, {"name": "未知", "style": "变化不明"})

    main_name = f"{upper_info['name']}上{lower_info['name']}下"
    changed_name = f"{changed_upper_info['name']}上{changed_lower_info['name']}下"

    moving_text = "无明显动爻" if not moving_positions else "动爻在第" + "、".join(map(str, moving_positions)) + "次"

    style = f"""
本卦：{main_name}
上卦气质：{upper_info['style']}
下卦气质：{lower_info['style']}
变卦：{changed_name}
变化方向：{changed_upper_info['style']} / {changed_lower_info['style']}
动爻：{moving_text}
"""

    return {
        "main_name": main_name,
        "changed_name": changed_name,
        "moving_positions": moving_positions,
        "style": style.strip()
    }

def call_deepseek(prompt):
    if OpenAI is None:
        print("OpenAI package not installed. Run: pip install openai")
        return None

    if not DEEPSEEK_API_KEY:
        print("DeepSeek API key not set. Using local fallback.")
        return None

    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com"
    )

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": """
You are the reading engine for a premium I Ching / Liu Yao decision-reading website.

You are not a chatbot.
You are not a therapist.
You are not a motivational writer.
You are not here to comfort the user.

Your task is to read the cast, identify the pattern, and return a result that feels specific, valuable, and difficult to reuse for another person.

CORE ROLE
- You are a strict traditional Liu Yao / I Ching divination master.
- For English, you also write with the atmosphere of a premium tarot / mystic reading website.
- For Chinese, you write like a serious 六爻断卦师傅：直接、清楚、有判断，不鸡汤。
- The product is paid. The paid answer must feel worth paying for.

NON-NEGOTIABLE JUDGMENT RULES
- Judgment comes before advice.
- Never make a bad cast sound good.
- Never create hope if the cast does not support hope.
- Never add a comforting ending after a negative judgment.
- If the cast points to failure, delay, rejection, loss, separation, reversal, exhaustion, weakening, or low probability, say it plainly.
- If the cast points to success, completion, union, return, movement, opening, or support, say it plainly.
- Do not default to “possible but delayed”. That is forbidden unless the cast actually supports it.
- Do not default to “key person”, “trust issue”, “communication”, “documents”, “one to two weeks”, or “hidden opportunity”.

WHAT YOU MAY USE
Use only the information provided by the user prompt:
- the user's exact question
- language
- topic inferred by the program
- cast time
- six coin results
- main hexagram / changed hexagram from upper and lower trigrams
- moving lines
- trigram tendencies

WHAT YOU MUST NOT INVENT
Do not fabricate:
- Na Jia stems/branches
- Six Relatives
- Six Spirits
- Shi/Ying positions
- month/day strength
- Yong Shen placement
- exact dates
- names, genders, jobs, family roles, or identities not shown by the question

If classical Liu Yao data is not provided, say or imply that the judgment is based on hexagram image, moving lines, and change tendency. Do not pretend to have more technical data than you were given.

TRADITIONAL READING LOGIC
When judging, silently examine:
- 本卦: current pattern and present condition
- 变卦: where the matter is moving
- 动爻: break point, change point, or pressure point
- 上卦: outer condition / outside force / visible environment
- 下卦: inner foundation / user position / hidden base
- movement vs stillness
- whether the situation is opening, closing, blocked, scattered, reduced, stripped, returning, waiting, joining, conflicting, completing, or failing to complete

PREMIUM VALUE RULE
The paid answer must reveal at least four things that the free answer does not fully explain:
1. the actual pattern in the hexagram,
2. what is hidden beneath the surface,
3. the real point of resistance,
4. what would change the outcome,
5. what to do next,
6. what to avoid.

The user should feel: “This understood my situation and gave me something I did not already know.”
This does not mean making the user happy. A hard answer can still be valuable if it is precise.

ANTI-TEMPLATE RULE
Every reading must feel impossible to copy-paste into another person's question.
Vary:
- opening sentence
- hidden influence
- timing logic
- obstacle
- advice
- closing line
- imagery
- rhythm

Do not repeatedly use these phrases:
- there is still room to move
- not fully in your hands
- key person
- trust issue
- communication is key
- one to two weeks
- wait patiently
- hidden opportunity
- final word
- decision maker
- proof of value
unless the exact cast and question justify them.

ENGLISH STYLE
For English, write like a premium tarot / I Ching reading website:
- mysterious but clear
- elegant but useful
- emotionally resonant but not sugary
- symbolic but not vague
- direct enough to help a real decision

Good English phrases:
- The Pattern
- What Lies Beneath
- The Turning Point
- The Door That Opens
- The Door That Closes
- Walk With the Hexagram
- The cast does not reject this, but it refuses to rush it.
- This is not a closed door; it is a guarded one.
- The pressure is not where you think it is.
- The hexagram does not ask for more force. It asks for better timing.

Forbidden English style:
- therapy language
- generic coaching
- corporate analysis
- “based on the data”
- “as an AI”
- “the universe wants...”
- “everything happens for a reason”
- exaggerated fate/destiny claims

CHINESE STYLE
For Chinese, write like a real 六爻断卦师傅:
- 先断成败，再讲依据。
- 能成就说能成，难成就说难成。
- 不要为了好听而转弯。
- 可以有神秘感，但不要空泛。
- 少鸡汤，多判断。
- 语言要像“师傅在断卦”，不是心理咨询。

Chinese preferred wording:
- 此卦不主快成。
- 这件事有门，但不在你强推。
- 问事业，主先阻后通。
- 问感情，主心意不齐。
- 问审批，主拖延反复。
- 动处即是变处。
- 变卦所指，是后面真正的走向。
- 此事不是没机会，而是时机未合。
- 若三个月为限，前段不宜急催，中后段才见动静。

OUTPUT FORMAT
Return valid JSON only.
No markdown fences.
No explanation outside JSON.
JSON must contain exactly:
{
  "free": "...",
  "paid": "..."
}
"""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.62,
            max_tokens=1800
        )

        return response.choices[0].message.content

    except Exception as e:
        print("DeepSeek API error:", repr(e))
        return None

def parse_ai_json(raw):
    if not raw:
        return None

    try:
        return json.loads(raw)
    except:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            return None

    return None


def local_fallback(question, topic, emotion_level, lang):
    if lang == "en":
        free = """Overall Energy: ★★★☆☆

The Pattern
This cast shows movement, but not a clean opening. The matter is still being shaped beneath the surface.

What Lies Beneath
The obstacle is not only effort. Something in the timing, response, or outside condition has not settled.

A Sign To Watch
If the situation moves, it will first appear as a small change in tone, timing, or access — not a final answer.

The complete reading reveals:
• what the hexagram is really holding back
• what changes the outcome
• where the resistance sits
• what action the cast favors"""
        paid = """I. The Pattern

This cast does not give a clean yes or no. It shows a matter that can still move, but only after the pressure underneath changes. The first layer is not rejection; it is resistance.

II. What Lies Beneath

The hidden current is a mismatch between desire and timing. One side wants movement, while the surrounding condition is not yet ready to support it. Pushing harder may create more friction instead of more progress.

III. The Turning Point

The turning point appears when the situation gives a concrete sign rather than a vague feeling: a response, an opening, a request, a change in tone, or a visible shift in access. Without that sign, the matter remains half-formed.

IV. The Door That Opens

The door opens through precision, not force. A clearer question, cleaner evidence, or a better-timed move has more power than repeated pressure.

V. Walk With the Hexagram

Do one direct action, then stop watching the door every hour. If the cast is right, movement will reveal itself through a small but unmistakable change.

VI. One Final Observation

This answer is not hidden because it is far away. It is hidden because the moment has not finished arranging itself."""
    else:
        free = """结果倾向：★★★☆☆

本卦：当前卦象有动，但不是直通之象。

一句核心结论：此事仍有变化空间，但不能靠强推立刻成。

一句反转信息：真正卡住的不是愿望本身，而是时机、回应或外部条件未定。

一句未来信号：若有进展，先见小动静，再见结果。

完整版将揭示：
• 卦象真正含义
• 关键因素
• 真正阻力
• 时间窗口"""
        paid = """一、最终判断

此卦不主立刻成，也不主完全无望。它显示事情仍有动处，但要等外部条件松动后才会有明确结果。若问短期，偏拖；若问后续，仍可观察。

二、卦象依据

本卦有动，说明事情不是死局；但动不等于立成。动处即是变处，表示中间会出现调整、反复或重新判断。变卦所指，是后面真正的走向，现在还没完全落定。

三、真正阻力

阻力不一定在你愿不愿意，而在条件是否已经配齐。若强推，反而容易让局势显得急促。此卦更怕乱动，不怕暂缓。

四、关键人物或关键因素

关键不一定是某个人，而是一个“能否落地”的条件：时间、名额、回应、流程、证据或对方态度。它不出现，事情就只能停在半明半暗处。

五、未来变化

若有转机，先不会直接给最终结果，而是先出现一个小信号：有人回应、流程变化、态度松动、信息补齐。看见这个信号，才说明卦气开始转活。

六、下一步行动

先做一件最有效的推进，不要反复催。该补证据补证据，该换方式换方式。此卦要你顺势找入口，不是硬撞门。"""

    return {"free": free, "paid": paid}

def build_prompt(lang, question, cast_time, words, topic, emotion_level, seed_key, hexagram_info):
    lang_name = "Chinese" if lang == "zh" else "English"
    topic_name = topic_label(topic, lang)

    return f"""
You must output valid JSON only.

Language: {lang_name}
Topic inferred by program: {topic_name}
Emotion level: {emotion_level}
Seed key: {seed_key}

User question:
{question}

Casting time:
{cast_time}

Six coin results, from first to sixth:
{words}

Available hexagram structure:
{hexagram_info["style"]}

V3 READING OBJECTIVE
This is not a generic AI answer.
This is a premium I Ching / Liu Yao decision reading.
The free answer must create curiosity and provide useful direction.
The paid answer must feel deeper, sharper, more personal, and worth AU$1.99.

FIRST, SILENTLY CLASSIFY THE REAL QUESTION
Do not rely only on the topic label.
Infer the real objective from the user's wording:
- Will this happen?
- Should I do this?
- Is this person sincere?
- Will I be approved?
- Will I pass?
- Will I get money / lose money?
- Will I get the offer?
- Is this relationship continuing or ending?
- Is timing favorable?
- What is blocking me?

Then judge the cast according to that objective.

JUDGMENT METHOD
Use only the available hexagram information:
- 本卦 = present pattern
- 变卦 = future direction
- 动爻 = pressure point / change point
- 上卦 = outer condition
- 下卦 = inner base
- trigram tendencies = nature of movement

Do not invent technical Liu Yao data not provided.
If needed, state that the judgment is based on hexagram image, movement, and change tendency.

PROBABILITY / TENDENCY
Use a tendency rather than fake precision.
If probability is useful, use one of these bands only:
- very low: 10-20%
- low: 30-40%
- mixed: around 50%
- moderate: 60-70%
- strong: 75-85%
- very strong: 90%+
Do not default to 60-70%.

TIMING
Match the user's time horizon.
- If the user asks three months, discuss early / middle / late phase.
- If the user asks next month, discuss weeks.
- If the user asks this year, discuss seasons or quarters.
- If no horizon is given, use broad timing only.
Do not always say one to two weeks.
Do not invent exact dates.

FREE READING — ENGLISH
If Language is English, free must be 85-130 words.
It must use this structure exactly:

Overall Energy: ★★★☆☆

The Pattern
[1-2 sentences. Direct answer, mysterious but clear.]

What Lies Beneath
[1-2 sentences. Hidden influence or reversal.]

A Sign To Watch
[1 sentence. Observable signal or timing clue.]

The complete reading reveals:
• the deeper pattern
• what is hidden beneath the surface
• what changes the outcome
• the action this cast favors

Do not use headings like Conclusion, Current State, Key Reminder.
Do not reveal all paid logic.

FREE READING — CHINESE
If Language is Chinese, free must be 120-180 Chinese characters.
It must use this structure exactly:

结果倾向：★★★☆☆

本卦：XXX

一句核心结论。

一句反转信息。

一句未来信号。

完整版将揭示：
• 卦象真正含义
• 关键因素
• 真正阻力
• 时间窗口

PAID READING — ENGLISH
If Language is English, paid must be 520-780 words.
Use exactly these six sections:

I. The Pattern
II. What Lies Beneath
III. The Turning Point
IV. The Door That Opens or Closes
V. Walk With the Hexagram
VI. One Final Observation

Requirements:
- First paragraph must directly answer the user’s question.
- It must include a clear tendency: likely / unlikely / delayed / blocked / possible / strong / weak.
- It must explain the main hexagram and changed hexagram in plain mystical language.
- It must include one hidden influence not obvious from the question.
- It must include one condition that would change the outcome.
- It must include one action to take and one action to avoid.
- It must not sound like a business report or therapy session.
- It must not repeat the free answer with more words.
- It must feel specific to this exact cast.

English paid style examples:
Good:
“The cast does not close the door, but it refuses to open it under pressure.”
“The movement is not absent; it is guarded.”
“The real obstacle is not desire, but the condition under which the other side feels safe to move.”
“This is a door that opens through timing, not force.”

Bad:
“Communication is key.”
“Stay patient and trust the process.”
“You should believe in yourself.”
“There is still hope.”

PAID READING — CHINESE
If Language is Chinese, paid must be 700-1050 Chinese characters.
Use exactly these six sections:

一、最终判断
二、卦象依据
三、真正阻力
四、关键人物或关键因素
五、未来变化
六、下一步行动

Requirements:
- 第一段第一句必须直接回答用户问题。
- 要明确：偏成 / 偏难 / 会拖 / 会反复 / 不主快成 / 可继续 / 不宜强求。
- 必须结合本卦、变卦、动爻说明，不要像心理分析。
- 如果卦不好，直接说不好。
- 如果卦好，直接说好，但说明成在哪里。
- 不要每次都说“关键人物”。如果不是人，就说关键因素。
- 不要每次都说“两周”。
- 不要鸡汤结尾。

CHINESE STYLE EXAMPLES
Good:
“此卦不主快成，三个月内有动静，但未必一次定局。”
“动处在前段，说明一开始就有变化，但变化未必等于结果。”
“变卦转坤，主承接、等待、顺势，不主强攻。”
“此事要靠条件齐，不靠反复催。”

Bad:
“保持积极心态。”
“相信自己。”
“宇宙会安排。”
“未来会越来越好。”

ANTI-REPETITION RULE
Do not use the same wording, same obstacle, same timing, or same closing style for different readings.
The wording must follow the cast.

Return exactly this JSON:
{{
  "free": "...",
  "paid": "..."
}}
"""


def mark_paid(seed_key, stripe_session_id=None, amount_total=None, currency=None):
    """Record a verified paid Checkout Session.

    This function is intentionally defensive because the local SQLite file
    may have been created before the payments table had its current shape.
    """
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    now = datetime.now().isoformat()

    try:
        cur.execute("""
            SELECT id FROM payments
            WHERE seed_key=?
            LIMIT 1
        """, (seed_key,))
        row = cur.fetchone()

        if row:
            cur.execute("""
                UPDATE payments
                SET stripe_session_id=?,
                    status='paid',
                    amount_total=?,
                    currency=?,
                    paid_at=?
                WHERE seed_key=?
            """, (stripe_session_id, amount_total, currency, now, seed_key))
        else:
            cur.execute("""
                INSERT INTO payments
                (seed_key, stripe_session_id, status, amount_total, currency, created_at, paid_at)
                VALUES (?, ?, 'paid', ?, ?, ?, ?)
            """, (seed_key, stripe_session_id, amount_total, currency, now, now))

        conn.commit()
        print("PAYMENT RECORDED:", seed_key, stripe_session_id, flush=True)
    finally:
        conn.close()

def has_paid(seed_key):
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM payments
        WHERE seed_key=? AND status='paid'
        LIMIT 1
    """, (seed_key,))
    row = cur.fetchone()
    conn.close()
    return row is not None

def get_cached_reading(seed_key):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT free_text, paid_text FROM readings WHERE seed_key=?", (seed_key,))
    row = cur.fetchone()
    conn.close()

    if row:
        return {"free": row[0], "paid": row[1]}
    return None


def get_reading_by_seed(seed_key):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT lang, question, cast_time, free_text, paid_text
        FROM readings
        WHERE seed_key=?
    """, (seed_key,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "lang": row[0],
        "question": row[1],
        "cast_time": row[2],
        "free": row[3],
        "paid": row[4],
    }


def save_reading(seed_key, lang, question, cast_time, words, topic, emotion_level, free_text, paid_text):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO readings
        (seed_key, lang, question, cast_time, words, topic, emotion_level, free_text, paid_text, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        seed_key,
        lang,
        question,
        cast_time,
        ",".join(words),
        topic,
        emotion_level,
        free_text,
        paid_text,
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()


def generate_reading(question, cast_time, words, lang, hour):
    topic = detect_topic(question)
    emotion_level = detect_emotion_level(question, hour)

    hexagram_info = build_hexagram(words)

    # Cache rule:
    # same language + same question + same casting time + same six results = same reading.
    # This keeps the answer stable for the same cast, while a different question/time/cast still creates a new result.
    normalized_question = " ".join(question.strip().split())
    normalized_words = ",".join(str(w).strip() for w in words)
    seed_raw = f"{lang}|{normalized_question}|{cast_time}|{normalized_words}"
    seed_key = stable_hash(seed_raw)

    cached = get_cached_reading(seed_key)
    if cached:
        print("CACHE HIT:", seed_key, flush=True)
        cached["seed_key"] = seed_key
        return cached

    print("NEW READING - calling DeepSeek:", seed_key, flush=True)
    prompt = build_prompt(lang, question, cast_time, words, topic, emotion_level, seed_key, hexagram_info)
    raw = call_deepseek(prompt)
    parsed = parse_ai_json(raw)

    if not parsed or "free" not in parsed or "paid" not in parsed:
        parsed = local_fallback(question, topic, emotion_level, lang)

    free_text = parsed["free"].strip()
    paid_text = parsed["paid"].strip()

    save_reading(seed_key, lang, question, cast_time, words, topic, emotion_level, free_text, paid_text)

    return {
        "seed_key": seed_key,
        "free": free_text,
        "paid": paid_text
    }




@app.route("/create-checkout-session/<seed_key>", methods=["POST"])
def create_checkout_session(seed_key):
    data = get_reading_by_seed(seed_key)
    if not data:
        abort(404)

    if has_paid(seed_key):
        return redirect(url_for("reading_page", seed_key=seed_key))

    if stripe is None or not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        return redirect(url_for("reading_page", seed_key=seed_key))

    try:
        checkout_session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=(["card", "alipay"] if STRIPE_ENABLE_ALIPAY else ["card"]),
            line_items=[
                {
                    "price": STRIPE_PRICE_ID,
                    "quantity": 1,
                }
            ],
            success_url=url_for("payment_success", seed_key=seed_key, _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=url_for("reading_page", seed_key=seed_key, _external=True),
            metadata={
                "seed_key": seed_key
            }
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        print("Stripe checkout error:", repr(e))
        return redirect(url_for("reading_page", seed_key=seed_key))


@app.route("/payment/success/<seed_key>", methods=["GET"])
def payment_success(seed_key):
    print("===================================", flush=True)
    print("ENTER payment_success", flush=True)
    print("seed_key =", seed_key, flush=True)
    print("args =", request.args, flush=True)
    print("===================================", flush=True)

    data = get_reading_by_seed(seed_key)
    if not data:
        abort(404)

    session_id = request.args.get("session_id", "").strip()
    print("session_id =", session_id, flush=True)

    if not session_id or stripe is None or not STRIPE_SECRET_KEY:
        print("NO SESSION ID / STRIPE NOT CONFIGURED", flush=True)
        return redirect(url_for("reading_page", seed_key=seed_key))

    try:
        session = stripe.checkout.Session.retrieve(session_id)

        # Stripe objects are not always normal Python dicts.
        # Convert to a plain dict first so .get() works reliably.
        if hasattr(session, "to_dict_recursive"):
            session_data = session.to_dict_recursive()
        elif hasattr(session, "to_dict"):
            session_data = session.to_dict()
        else:
            session_data = dict(session)

        payment_status = session_data.get("payment_status")
        metadata = session_data.get("metadata") or {}
        session_seed = metadata.get("seed_key")
        session_id_from_stripe = session_data.get("id", session_id)
        amount_total = session_data.get("amount_total")
        currency = session_data.get("currency")

        print("payment_status =", payment_status, flush=True)
        print("metadata =", metadata, flush=True)
        print("session_seed =", session_seed, flush=True)

        if session_seed == seed_key and payment_status == "paid":
            print("MARK PAID", flush=True)

            mark_paid(
                seed_key=seed_key,
                stripe_session_id=session_id_from_stripe,
                amount_total=amount_total,
                currency=currency,
            )

            print("PAYMENT RECORDED AND REDIRECTING", flush=True)
            return redirect(url_for("reading_page", seed_key=seed_key))

        print("VERIFY FAILED", flush=True)
        print("session_seed:", session_seed, "expected:", seed_key, "status:", payment_status, flush=True)

    except Exception as e:
        print("VERIFY ERROR", flush=True)
        print(repr(e), flush=True)

    return redirect(url_for("reading_page", seed_key=seed_key))


@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    if stripe is None or not STRIPE_WEBHOOK_SECRET:
        return jsonify({"ok": False, "reason": "webhook not configured"}), 400

    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except Exception as e:
        print("Stripe webhook signature error:", repr(e))
        return jsonify({"ok": False}), 400

    event_type = event.get("type") if isinstance(event, dict) else event["type"]

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]

        if hasattr(session, "to_dict_recursive"):
            session_data = session.to_dict_recursive()
        elif hasattr(session, "to_dict"):
            session_data = session.to_dict()
        else:
            session_data = dict(session)

        metadata = session_data.get("metadata") or {}
        seed_key = metadata.get("seed_key")

        if seed_key and session_data.get("payment_status") == "paid":
            mark_paid(
                seed_key=seed_key,
                stripe_session_id=session_data.get("id"),
                amount_total=session_data.get("amount_total"),
                currency=session_data.get("currency"),
            )

    return jsonify({"received": True})


@app.route("/", methods=["GET", "POST"])
def home():
    lang = request.form.get("lang", "en")
    if lang not in TEXTS:
        lang = "en"

    t = TEXTS[lang]
    now = datetime.now()

    result = None
    paid_result = None
    question = ""
    cast_time = ""

    if request.method == "POST":
        action = request.form.get("submit_action", "")

        question = request.form.get("question", "").strip()

        words = []
        for i in range(1, 7):
            words.append(request.form.get(f"word{i}", "").strip())

        if action == "cast" and question and all(w != "" for w in words):
            year = request.form.get("year", "").strip()
            month = request.form.get("month", "").strip()
            day = request.form.get("day", "").strip()
            hour = request.form.get("hour", "").strip()

            if year and month and day and hour:
                cast_time = f"{year}/{month}/{day} {hour}:00"

                reading = generate_reading(
                    question,
                    cast_time,
                    words,
                    lang,
                    hour
                )

                return redirect(url_for("reading_page", seed_key=reading["seed_key"]))

    return render_template_string(
        HTML,
        t=t,
        lang=lang,
        current_year=now.strftime("%Y"),
        current_month=now.strftime("%m"),
        current_day=now.strftime("%d"),
        current_hour=now.strftime("%H"),
        result=result,
        paid_result=paid_result,
        question=question,
        cast_time=cast_time,
        share_url=None,
        seed_key="",
        paid_unlocked=False,
        stripe_enabled=bool(stripe is not None and STRIPE_SECRET_KEY and STRIPE_PRICE_ID),
        alipay_payment_url=ALIPAY_PAYMENT_URL,
        wechat_payment_url=WECHAT_PAYMENT_URL,
        alipay_qr_url=ALIPAY_QR_URL,
        wechat_qr_url=WECHAT_QR_URL
    )


@app.route("/reading/<seed_key>", methods=["GET"])
def reading_page(seed_key):
    data = get_reading_by_seed(seed_key)
    if not data:
        abort(404)

    lang = data["lang"]
    if lang not in TEXTS:
        lang = "en"

    t = TEXTS[lang]
    now = datetime.now()

    return render_template_string(
        HTML,
        t=t,
        lang=lang,
        current_year=now.strftime("%Y"),
        current_month=now.strftime("%m"),
        current_day=now.strftime("%d"),
        current_hour=now.strftime("%H"),
        result=data["free"],
        paid_result=data["paid"],
        question=data["question"],
        cast_time=data["cast_time"],
        share_url=url_for("share_page", seed_key=seed_key),
        seed_key=seed_key,
        paid_unlocked=has_paid(seed_key),
        stripe_enabled=bool(stripe is not None and STRIPE_SECRET_KEY and STRIPE_PRICE_ID),
        alipay_payment_url=ALIPAY_PAYMENT_URL,
        wechat_payment_url=WECHAT_PAYMENT_URL,
        alipay_qr_url=ALIPAY_QR_URL,
        wechat_qr_url=WECHAT_QR_URL
    )


SHARE_HTML = """
<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ "分享卦卡" if lang=="zh" else "Share Reading Card" }}</title>
<style>
:root{
    --gold:#d4af37;
    --gold2:#f5d48a;
    --text:#f3e7c9;
    --muted:#bca98a;
    --font-body:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Noto Sans SC","Segoe UI",Arial,sans-serif;
    --font-title:"Noto Serif SC","Source Han Serif SC","Songti SC","STSong","KaiTi",serif;
}
*{ box-sizing:border-box; }
body{
    margin:0;
    min-height:100vh;
    background:radial-gradient(circle at 50% -8%, rgba(214,173,79,.24), transparent 48%), linear-gradient(180deg,#100b07,#050505 78%);
    color:var(--text);
    font-family:var(--font-body);
    padding:28px 16px 42px;
}
.wrap{
    max-width:520px;
    margin:0 auto;
}
.card{
    position:relative;
    overflow:hidden;
    border-radius:32px;
    padding:30px 26px 28px;
    border:1px solid rgba(212,175,55,.36);
    background:linear-gradient(180deg,rgba(28,19,12,.96),rgba(5,5,5,.98));
    box-shadow:0 28px 90px rgba(0,0,0,.72);
}
.card:before{
    content:"";
    position:absolute;
    inset:-30% -20% auto;
    height:180px;
    background:radial-gradient(circle,rgba(245,212,138,.18),transparent 62%);
    pointer-events:none;
}
.brand{
    position:relative;
    text-align:center;
    margin-bottom:24px;
}
.brand h1{
    margin:0;
    font-family:var(--font-title);
    color:var(--gold2);
    font-size:32px;
    letter-spacing:.08em;
    font-weight:700;
}
.brand p{
    margin:8px 0 0;
    color:var(--muted);
    font-size:13px;
    letter-spacing:.08em;
}
.section{
    position:relative;
    margin:18px 0;
    padding:16px 16px;
    border-radius:20px;
    background:rgba(255,255,255,.035);
    border:1px solid rgba(212,175,55,.13);
}
.label{
    color:var(--gold2);
    font-size:14px;
    font-weight:800;
    margin-bottom:8px;
    letter-spacing:.05em;
}
.value{
    color:#f4e8cf;
    font-size:17px;
    line-height:1.8;
    white-space:pre-line;
}
.result-text{
    font-size:16.5px;
    line-height:1.9;
    color:#f0dfbf;
    white-space:pre-line;
}
.qr-area{
    display:flex;
    align-items:center;
    gap:18px;
    margin-top:24px;
    padding-top:22px;
    border-top:1px solid rgba(212,175,55,.22);
}
.qr{
    width:118px;
    height:118px;
    padding:8px;
    border-radius:18px;
    background:#f7f0df;
    flex:0 0 auto;
}
.qr img{
    width:100%;
    height:100%;
    display:block;
}
.qr-copy{
    flex:1;
    color:#d8c6a1;
    font-size:14px;
    line-height:1.7;
}
.qr-copy strong{
    display:block;
    color:var(--gold2);
    font-size:16px;
    margin-bottom:6px;
}
.actions{
    display:flex;
    gap:12px;
    margin-top:20px;
}
.actions a,
.actions button{
    flex:1;
    border:none;
    border-radius:999px;
    min-height:52px;
    padding:0 16px;
    display:flex;
    align-items:center;
    justify-content:center;
    text-decoration:none;
    font-weight:800;
    font-size:15px;
    cursor:pointer;
}
.primary{
    background:linear-gradient(90deg,#8d5d17,#e1b85b,#8d5d17);
    color:#050505;
}
.secondary{
    background:rgba(255,255,255,.04);
    color:#e8d8b7;
    border:1px solid rgba(212,175,55,.28)!important;
}
.tip{
    text-align:center;
    color:#9d8b6f;
    font-size:13px;
    margin:18px 0 0;
    line-height:1.7;
}
@media(max-width:520px){
    body{ padding:18px 12px 34px; }
    .card{ padding:26px 18px 22px; border-radius:26px; }
    .brand h1{ font-size:28px; }
    .qr-area{ align-items:flex-start; }
    .qr{ width:104px; height:104px; }
    .actions{ flex-direction:column; }
}
@media print{
    .actions,.tip{ display:none; }
    body{ background:#050505; }
}
</style>
</head>
<body>
<div class="wrap">
    <div class="card" id="shareCard">
        <div class="brand">
            <h1>{{ "你的答案之书" if lang=="zh" else "Book of Answers" }}</h1>
            <p>{{ "一卦一问 · 此刻有答" if lang=="zh" else "One question · One cast" }}</p>
        </div>

        <div class="section">
            <div class="label">{{ "问卦" if lang=="zh" else "Question" }}</div>
            <div class="value">{{ question }}</div>
        </div>

        <div class="section">
            <div class="label">{{ "时间" if lang=="zh" else "Time" }}</div>
            <div class="value">{{ cast_time }}</div>
        </div>

        <div class="section">
            <div class="label">{{ "结果" if lang=="zh" else "Result" }}</div>
            <div class="result-text">{{ summary }}</div>
        </div>

        <div class="qr-area">
            <div class="qr">
                <img src="{{ qr_url }}" alt="QR Code">
            </div>
            <div class="qr-copy">
                <strong>{{ "扫码查看这一卦" if lang=="zh" else "Scan to open this reading" }}</strong>
                {{ "长按保存这张卡片，或截图分享到小红书 / 微信。" if lang=="zh" else "Save or screenshot this card to share." }}
            </div>
        </div>
    </div>

    <div class="actions">
        <a class="primary" href="{{ reading_url }}">{{ "打开完整页面" if lang=="zh" else "Open Reading" }}</a>
        <button class="secondary" type="button" onclick="copyLink()">{{ "复制链接" if lang=="zh" else "Copy Link" }}</button>
    </div>

    <div class="tip">
        {{ "提示：手机端可直接截图保存为打卡照。" if lang=="zh" else "Tip: On mobile, screenshot this card to save it as an image." }}
    </div>
</div>

<script>
function copyLink(){
    const link = "{{ reading_url }}";
    if(navigator.clipboard && navigator.clipboard.writeText){
        navigator.clipboard.writeText(link).then(function(){
            alert("{{ '链接已复制。' if lang=='zh' else 'Link copied.' }}");
        });
    }else{
        prompt("{{ '复制这个链接：' if lang=='zh' else 'Copy this link:' }}", link);
    }
}
</script>
</body>
</html>
"""

@app.route("/share/<seed_key>", methods=["GET"])
def share_page(seed_key):
    data = get_reading_by_seed(seed_key)
    if not data:
        abort(404)

    lang = data["lang"] if data["lang"] in TEXTS else "en"
    reading_url = url_for("reading_page", seed_key=seed_key, _external=True)
    qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=" + quote_plus(reading_url)

    return render_template_string(
        SHARE_HTML,
        lang=lang,
        question=data["question"],
        cast_time=data["cast_time"],
        summary=data["free"],
        reading_url=reading_url,
        qr_url=qr_url
    )


if __name__ == "__main__":
    init_db()
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "0") == "1"
    )
