from flask import Flask, request, render_template_string, redirect, url_for, abort
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

app = Flask(__name__)
DB_NAME = "readings.db"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

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
        "title": "Book of Answers",
        "subtitle": "Three coins. One question.",
        "guide_title": "Before You Begin",
        "guide_text": "Do not rush into the question.\n\nBring your attention to the thing you cannot quite let go of.\n\nPrepare 3 identical coins, or any 3 identical objects with two distinguishable sides.\n\nToss them 6 times.Each time, select how many number/front sides face upward.\n\nDo not ask the same question again and again.The first reading is often closest to your present intuition.",
        "question": "Your Question",
        "question_ph": "Example: Can I get an offer within 3 months? Should I keep holding onto this person? Can I truly secure this project?",
        "time": "This Moment",
        "time_ph": "Current time by default. You may edit it.",
        "time_hint": "Example: 9PM on May 17, 2026 → 2026 / 05 / 17 / 21",
        "coin_title": "The Six Falls",
        "coin_hint": "Before they fall, hold your true question clearly in mind.Select how many number/front sides face upward each time.",
        "yao": "Throw {n}",
        "submit": "Read This Cast",
        "select": "Select",
        "report": "The Answer Appears",
        "asked": "You asked",
        "time_result": "Casting time",
        "full_title": "Full Reading",
        "full_hint": "The full version expands the situation, hidden resistance, future movement, and next step.",
        "full_btn": "View Full Reading",
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
            <span>年</span>

            <input name="month" value="{{ current_month }}" maxlength="2">
            <span>月</span>

            <input name="day" value="{{ current_day }}" maxlength="2">
            <span>日</span>

            <input name="hour" value="{{ current_hour }}" maxlength="2">
            <span>时</span>
        </div>

        <div class="time-tip">{{ t['time_hint'] }}</div>

        <label>{{ t['coin_title'] }}</label>

       <div class="coin-mini-tip">
        {{ t['coin_hint'] }}
        <span class="manual-note">
            {{ "当然，自己亲手掷出的这一卦，往往更接近答案。" if lang=="zh" else "A reading cast by your own hands is often closer to your true state of mind." }}
        </span>
        </div>
        <div class="cast-mode">
            <button type="button" class="mode-btn active" id="manualBtn" onclick="setManual()">
                {{ "我自己来" if lang=="zh" else "I’ll Do It" }}
            </button>

            <button type="button" class="mode-btn" id="autoBtn" onclick="autoCast()">
                {{ "交给系统" if lang=="zh" else "Let Fate Decide" }}
            </button>
        </div>


        <div id="loadingModal" class="loading-modal">
            <div class="loading-box">
                <div class="loading-symbol">☯</div>
                <h3>{{ "吕主正在推演此卦" if lang=="zh" else "The reading is being revealed" }}</h3>
                <p>
                    {{ "本卦、变卦与动爻正在显化。请稍候片刻，不要关闭页面。" if lang=="zh" else "The main hexagram, changing hexagram, and moving lines are forming. Please keep this page open." }}
                </p>
                <div class="loading-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>

        <div id="autoModal" class="auto-modal">
            <div class="auto-box">
                <h3>{{ "交给系统" if lang=="zh" else "Let Fate Decide" }}</h3>
                <p id="autoMessage">
                    {{ "在开始之前，请心中默念真正想问的事。" if lang=="zh" else "Before we begin, hold your true question clearly in mind." }}
                </p>

                <div class="auto-coins">◐ ◑ ◒</div>
                <div id="autoResults" class="auto-results"></div>

                <button type="button" id="confirmAutoBtn" onclick="startAutoCast()">
                    {{ "我准备好了" if lang=="zh" else "I’m Ready" }}
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
                {{ "生成分享卡片" if lang=="zh" else "Create Share Card" }}
            </a>
            <button type="button" class="copy-link-btn" onclick="copyReadingLink()">
                {{ "复制本卦链接" if lang=="zh" else "Copy Reading Link" }}
            </button>
        </div>
        {% endif %}

        <div class="full-box">
            <h3>{{ t['full_title'] }}</h3>
            <p class="full-hint">{{ t['full_hint'] }}</p>
            <button type="button" onclick="openPayModal()">
                 {{ t['full_btn'] }}
        </button>

            <div id="paidBox" style="display:none;">
                <p class="save-tip">
                    {{ "提示：完整解析解锁后，请截图保存。刷新页面后会回到初始页面。" if lang=="zh" else "Tip: After unlocking, please take a screenshot to save your full reading. Refreshing the page will return to the initial page." }}
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
        : "The system is casting this reading for you.";

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
                : "All six throws are complete. The results have been filled in.";

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
        btn.innerText = pageLang === "zh" ? "吕主推演中..." : "Reading...";
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
    document.getElementById("payModal").classList.remove("show");
    document.getElementById("paidBox").style.display = "block";
}
</script>
<div id="payModal" class="auto-modal">
    <div class="auto-box">
        <h3>{{ "解锁完整解读" if lang=="zh" else "Unlock Full Reading" }}</h3>

        <p class="pay-note">
             {{ "完整版将揭示：" if lang=="zh" else "The full reading reveals:" }}
        </p>

        <div class="unlock-list">
            <div>• {{ "本卦与变卦真正指向" if lang=="zh" else "Main and changing hexagram meaning" }}</div>
            <div>• {{ "关键人物是谁" if lang=="zh" else "Who the key person is" }}</div>
            <div>• {{ "真正阻力在哪里" if lang=="zh" else "Where the real resistance lies" }}</div>
            <div>• {{ "未来时间窗口" if lang=="zh" else "Future timing window" }}</div>
            <div>• {{ "最优行动建议" if lang=="zh" else "Best next move" }}</div>
        </div>

        <div class="pay-actions">
            <button type="button" onclick="unlockPaidReading()">
                {{ "¥9.9 RMB 解锁完整解读" if lang=="zh" else "US$1.99 Unlock Full Reading" }}
            </button>

            <button type="button" class="mode-btn" onclick="closePayModal()">
                {{ "先不看" if lang=="zh" else "Not Now" }}
            </button>
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
You are a practical Liu Yao / I Ching reading engine.

Your priority is accuracy, structure, and useful judgment, not poetic writing.

Use the reasoning style of traditional Liu Yao divination, especially the logic associated with Bu Shi Zheng Zong and Zeng Shan Bu Yi:
- identify the matter type
- identify the useful focus of the question
- judge from hexagram structure, changing lines, motion and stillness
- consider the relation between the asker and the outside party
- translate the judgment into plain, useful advice

Important limits:
- Do NOT fabricate technical items that were not provided, such as exact Na Jia stems/branches, Six Relatives, Six Spirits, Shi/Ying positions, month/day strength, or exact Yong Shen placement.
- If those data are not available, use the provided hexagram structure and moving lines cautiously.
- Never pretend to quote Bu Shi Zheng Zong directly.
- Never use empty mystical prose.

Do NOT use these vague images or filler words unless directly necessary:
door, light, water, shadow, river, wind, stars, universe, energy, destiny, awakening, journey, frequency, mist.

Write like an experienced divination consultant:
- direct
- grounded
- specific
- slightly mysterious but not vague
- clear about tendency, obstruction, timing, and next action

Output valid JSON only.
"""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.88,
            max_tokens=1200
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
        free = """Result tendency: ★★★★☆

Conclusion: This is not closed. There is still room to move, but it will not be won by pressure alone.

Current state: You are close to the decision area, but the final word is not fully in your hands.

Key reminder: One person or one unresolved concern matters more than your effort itself.

The full reading reveals: the real resistance, the key person, the timing window, and your next move."""
        paid = """[1. Result tendency]
This matter has room to succeed, but the result is not completely settled. The tendency is favorable, though delayed. It is closer to "possible with the right move" than "already secured".

[2. Current situation]
The situation is not empty. You have already entered the field of consideration. The problem is that the final decision is still being weighed by another side.

[3. Real resistance]
The main resistance is not simply your ability. It is trust, timing, and whether the other side feels safe enough to move forward.

[4. Key factor]
The key is a person or condition that has not fully spoken yet. Do not assume silence means rejection.

[5. Future movement]
Watch for a signal in the next one to two weeks: a message, a request for confirmation, or a change in tone.

[6. Next step]
Do not rush or beg for certainty. Prepare one clear proof of your value, then create a reason for the other side to respond.

[Final sentence]
This is not about proving harder; it is about making the right person feel there is less risk in choosing you."""
    else:
        free = """结果倾向：★★★★☆

本卦：以当前卦象看，事情有机会。

但真正决定结果的人，并不是你正在接触的这个人。

未来两周会出现一个信号。

完整版将揭示：
• 卦象真正含义
• 关键人物
• 真正阻力
• 时间窗口"""
        paid = """一、结果倾向

这件事偏向有机会，大约六到七成。但不是已经稳拿，也不是越催越快。卦象显示，机会存在，但结果要经过一次筛选或确认。

二、卦象依据

本卦显示事情已经启动，变卦提示后续仍有调整空间。动爻代表中间过程会有变化，所以现在不是最终答案，而是一个正在被判断的阶段。

三、真正阻力

真正阻力不在你的能力，而在对方是否完全放心。对方可能认可你，但还在衡量风险、稳定性、配合度或后续成本。越急着证明，越容易显得不稳。

四、关键人物或关键因素

关键在一个能拍板、能推荐、或能影响评价的人身上。这个人未必是正在和你沟通的人，但他的态度会影响结果倾斜。你要解决的是他的顾虑，不只是表达自己的意愿。

五、未来变化

接下来一到两周，容易出现一次信号：追问细节、补材料、再次沟通，或有人态度松动。如果这段时间出现要求你补充说明的机会，反而是积极信号。

六、下一步行动

不要频繁催问。准备一个能降低对方顾虑的证明：成果、案例、数据、推荐或更清楚的方案。主动，但不要显得急。你要让对方觉得选你风险更低，而不是让对方感到压力更大。"""

    return {"free": free, "paid": paid}


def build_prompt(lang, question, cast_time, words, topic, emotion_level, seed_key, hexagram_info):
    lang_name = "Chinese" if lang == "zh" else "English"
    topic_name = topic_label(topic, lang)

    return f"""
You must output valid JSON only.

Language: {lang_name}
Topic: {topic_name}
Emotion level: {emotion_level}
Seed key: {seed_key}

User question:
{question}

Casting time:
{cast_time}

Six results, from first to sixth:
{words}

Available hexagram structure:
{hexagram_info["style"]}

Core requirement:
This product is a Liu Yao / I Ching decision-reading product.
The reading must be based on traditional divination reasoning, especially the judgment principles associated with Bu Shi Zheng Zong and Zeng Shan Bu Yi.

However, you only have the supplied hexagram structure and changing-line information.
Do NOT invent missing technical details such as exact Na Jia, Six Relatives, Six Spirits, Shi/Ying, month/day strength, or Yong Shen placement.
When you use traditional reasoning, phrase it as cautious judgment from the available hexagram, moving lines, and topic.

Style direction:
- Do not write like a novelist.
- Do not write decorative mystical prose.
- Do not overuse metaphor.
- Do not use vague imagery such as door, light, water, shadow, river, wind, stars, universe, energy, awakening, journey, mist.
- Do not say empty things like “follow your heart”, “trust the universe”, or “everything is still moving”.
- Write like a grounded Liu Yao consultant who gives a useful decision judgment.

The user wants an answer to the question, not a poem.

Free reading requirements:
1. The free reading is a teaser with a useful tendency, not a full answer.
2. It must include the main hexagram name, but do not use brackets like 《》 or [].
3. It must not explain changing lines, technical reasoning, or full hexagram logic.
4. It must not reveal the most valuable details.
5. Chinese length: 100-150 Chinese characters. Do not exceed 150 Chinese characters.
6. English length: 70-110 words.
7. Chinese format must be exactly:

结果倾向：
★★★★☆

本卦：XXX

一句核心结论。

一句反转信息。

一句未来信号。

完整版将揭示：
• 卦象真正含义
• 关键人物
• 真正阻力
• 时间窗口

8. English format must be similar:
Result tendency:
★★★★☆

Main hexagram: XXX

One direct conclusion.

One reversal / hidden factor.

One future signal.

The full reading reveals:
• True hexagram meaning
• Key person
• Real resistance
• Timing window

Paid reading requirements:
1. The paid reading must NOT repeat the free reading with more words.
2. It must be concrete, useful, and decision-oriented.
3. It must include the available hexagram structure naturally: 本卦, 变卦, 动爻.
4. It must use traditional Liu Yao judgment logic cautiously, but must not invent Na Jia, Six Relatives, Six Spirits, Shi/Ying, month/day strength, or Yong Shen if not provided.
5. Length:
   - Chinese: 650-950 Chinese characters.
   - English: 450-700 words.
6. Use this exact Chinese structure when lang is Chinese:

一、结果倾向

Give the direct tendency: likely / difficult / delayed / worth trying / not worth forcing. Include a rough probability when suitable.

二、卦象依据

Explain 本卦、变卦、动爻 from the provided hexagram structure. Keep it understandable.

三、真正阻力

Identify the real obstacle. For career, it may be decision authority, trust, timing, resources, competing priorities. For love, emotional hesitation, past hurt, unclear commitment. For money/legal, risk and evidence.

四、关键人物或关键因素

Tell the user what person/factor matters most. If unknown, say what type of person/factor it is, not a fake identity.

五、未来变化

Give a likely change window or signal. Do not promise exact events.

六、下一步行动

Give specific next actions. Tell the user whether to push, wait, clarify, prepare evidence, reduce exposure, or stop.

7. Use similar numbered headings in English.
8. Do not use markdown bold symbols like **text**.
9. Plain text only.

Important:
- Do not claim certainty.
- Do not say guaranteed, destined, must, absolutely.
- Do not mention AI.
- Do not write Markdown bold symbols like **text**.
- Plain text only.

Return exactly this JSON:
{{
  "free": "...",
  "paid": "..."
}}
"""


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

    seed_raw = f"{lang}|{question.strip()}|{cast_time}|{','.join(words)}|{topic}|{emotion_level}|{hexagram_info['main_name']}|{hexagram_info['changed_name']}"
    seed_key = stable_hash(seed_raw)
    cached = None
    #cached = get_cached_reading(seed_key)
    #if cached:
    #    cached["seed_key"] = seed_key
    #    return cached

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


@app.route("/", methods=["GET", "POST"])
def home():
    lang = request.form.get("lang", "zh")
    if lang not in TEXTS:
        lang = "zh"

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
        share_url=None
    )


@app.route("/reading/<seed_key>", methods=["GET"])
def reading_page(seed_key):
    data = get_reading_by_seed(seed_key)
    if not data:
        abort(404)

    lang = data["lang"]
    if lang not in TEXTS:
        lang = "zh"

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
        share_url=url_for("share_page", seed_key=seed_key)
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

    lang = data["lang"] if data["lang"] in TEXTS else "zh"
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
