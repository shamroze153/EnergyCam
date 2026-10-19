// The web page served at "/". Kept out of the .ino so Arduino's
// prototype generator does not mistake the JavaScript for C++.
#pragma once
#include <Arduino.h>

const char PAGE[] PROGMEM = R"rawliteral(<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tank Levels</title>
<style>
:root{--bg:#f2f4f7;--card:#fff;--text:#1c2530;--muted:#677382;--empty:#e2e7ed;--ok:#2e9e5b;--mid:#d99a00;--low:#d64545}
@media (prefers-color-scheme:dark){:root{--bg:#10151b;--card:#1a222b;--text:#e8edf2;--muted:#95a2b1;--empty:#2b3540}}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text)}
header{padding:16px;display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px}
h1{margin:0;font-size:1.5rem}
#status{color:var(--muted);font-size:.9rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px;padding:0 16px 16px}
.card{background:var(--card);border-radius:14px;padding:14px;text-align:center}
.name{font-weight:600;margin-bottom:10px}
.tank{position:relative;height:170px;max-width:100px;margin:0 auto;border-radius:10px;background:var(--empty);overflow:hidden}
.water{position:absolute;left:0;right:0;bottom:0;transition:height .8s}
.pct{font-size:2rem;font-weight:700;margin-top:8px}
.info{color:var(--muted);font-size:.9rem}
.warn{color:var(--low);font-weight:600}
</style></head><body>
<header><h1>Pani ki Tankiyan</h1><span id="status">Loading...</span></header>
<div class="grid" id="grid"></div>
<script>
function color(p){return p<25?'var(--low)':p<50?'var(--mid)':'var(--ok)'}
function card(t){
  if(t.percent<0) return '<div class="card"><div class="name">'+t.name+'</div><div class="tank"></div>'+
    '<div class="pct warn">--</div><div class="info warn">Sensor check karein</div></div>';
  var now=Math.round(t.liters*t.percent/100);
  return '<div class="card"><div class="name">'+t.name+'</div>'+
    '<div class="tank"><div class="water" style="height:'+t.percent+'%;background:'+color(t.percent)+'"></div></div>'+
    '<div class="pct" style="color:'+color(t.percent)+'">'+t.percent+'%</div>'+
    '<div class="info">'+now.toLocaleString()+' / '+t.liters.toLocaleString()+' L</div>'+
    (t.percent<25?'<div class="info warn">Pani kam hai</div>':'')+'</div>';
}
async function load(){
  try{
    var r=await fetch('/data',{cache:'no-store'});
    var d=await r.json();
    document.getElementById('grid').innerHTML=d.map(card).join('');
    document.getElementById('status').textContent='Updated '+new Date().toLocaleTimeString();
  }catch(e){document.getElementById('status').textContent='Connection lost, retrying...'}
}
load();setInterval(load,5000);
</script></body></html>)rawliteral";
