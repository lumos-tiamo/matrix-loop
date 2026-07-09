#!/usr/bin/env bash
# MatrixLoop 飞轮 · 端到端叙事化演示(主线:一条内容从趋势 → 定调 → 脚本 → 视频 → 发布 → 复盘)
# 用法:  bash scripts/demo_flywheel.sh            (默认账号 4 @money_talk,后端 :8010)
#        B=http://127.0.0.1:8010 ACCT=4 bash scripts/demo_flywheel.sh
set -uo pipefail
B="${B:-http://127.0.0.1:8010}"
ACCT="${ACCT:-4}"
PY=python3
c(){ printf '\n\033[1;36m========== %s ==========\033[0m\n' "$*"; }   # cyan banner
ok(){ printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
info(){ printf '  %s\n' "$*"; }
jqget(){ $PY -c "import sys,json;d=json.load(sys.stdin);print($1)" 2>/dev/null; }

c "0 · 体检"
H=$(curl -s --max-time 4 "$B/health"); [ -z "$H" ] && { echo "后端未启动($B)。先启动 backend。"; exit 1; }
ok "后端在线：$H"
ACC=$(curl -s --max-time 4 "$B/accounts/$ACCT")
HANDLE=$(printf '%s' "$ACC" | jqget "d.get('handle','?')")
info "演示账号：#$ACCT $HANDLE"

c "① 爬爆款 · 当下真实趋势(agent-reach 抓来的)"
TN=$(curl -s --max-time 5 "$B/flywheel" | jqget "next(s for s in d['steps'] if s['key']=='crawl')['count']")
info "飞轮 crawl 节点趋势数：$TN"
curl -s --max-time 5 "$B/trends?limit=4" | $PY -c "import sys,json
for t in json.load(sys.stdin): print('   •', t['distilled_topic'] or t['title'], '  ['+t['source']+']')" 2>/dev/null
ok "真实爆款已作为选题种子(按子垂类喂给脚本生成)"

c "② 定调 · 设频道 brief(web3 + crypto 子垂类 + 人设)"
curl -s --max-time 6 -X POST "$B/accounts/$ACCT/brief" -H "Content-Type: application/json" \
  -d '{"main_direction":"web3","sub_niches":["加密交易者","空投猎人","DeFi","Meme币玩家"],"tone":"punchy","language":"en","persona":"Nina","format":"faceless"}' >/dev/null
BR=$(curl -s --max-time 5 "$B/accounts/$ACCT/brief")
info "已保存定调：$(printf '%s' "$BR" | jqget "d['main_direction']+' · '+'、'.join(d['sub_niches'])+' · '+d['persona']")"
ok "定调完成"

c "③ 选题 + 脚本 · 真 LLM(吃定调 + 趋势 + 历史表现)"
info "跑一轮 Loop 生成选题(真 LLM,稍等)…"
curl -s --max-time 60 -X POST "$B/accounts/$ACCT/loop" >/dev/null
TID=$(curl -s "$B/accounts/$ACCT" | $PY -c "import sys,json;d=json.load(sys.stdin);print(next((dr['id'] for r in d['loop_runs'] for dr in r['drafts'] if dr['kind']=='topic' and dr['review_status']!='adopted'),''))" 2>/dev/null)
[ -z "$TID" ] && { echo "  未拿到选题草稿(可能 LLM 未配置);跳过后续内容步骤。"; TID=""; }
if [ -n "$TID" ]; then
  info "采纳选题 #$TID …"; curl -s -X POST "$B/drafts/$TID/status" -H "Content-Type: application/json" -d '{"review_status":"adopted"}' >/dev/null
  info "生成脚本(真 LLM)…"
  SID=$(curl -s --max-time 60 -X POST "$B/drafts/$TID/generate-script" | jqget "d.get('id','')")
  printf '\033[0;90m'; curl -s "$B/accounts/$ACCT" | $PY -c "import sys,json
d=json.load(sys.stdin)
for r in d['loop_runs']:
    for dr in r['drafts']:
        if str(dr.get('id'))=='$SID': print('   脚本预览：', (dr.get('content') or '')[:200].replace(chr(10),' '))" 2>/dev/null
  printf '\033[0m'; ok "真 LLM 脚本已生成(草稿 #$SID)"
fi

c "④ 视频 · 用量治理下生成(provider 门控 + 绝不发 fake)"
VID=""
if [ -n "${SID:-}" ]; then
  curl -s -X POST "$B/drafts/$SID/status" -H "Content-Type: application/json" -d '{"review_status":"adopted"}' >/dev/null
  VJSON=$(curl -s --max-time 30 -X POST "$B/accounts/$ACCT/generate-video" -H "Content-Type: application/json" -d "{\"script_draft_id\":$SID}")
  VID=$(printf '%s' "$VJSON" | jqget "d.get('id','')")
  printf '%s' "$VJSON" | $PY -c "import sys,json;v=json.load(sys.stdin);print('   成片：', {k:v.get(k) for k in ('id','provider','status','review_status','cost','media_url')})" 2>/dev/null
  ok "成片已生成(provider=fake 为占位;配 seedance 后即真视频到 /media)"
fi

c "⑤ 发布 · 人在环 + autopilot(此处诚实展示门控)"
if [ -n "$VID" ]; then
  curl -s -X POST "$B/video-assets/$VID/status" -H "Content-Type: application/json" -d '{"review_status":"approved"}' >/dev/null
  info "已人工审核通过成片 #$VID"
  RC=$(curl -s -o /tmp/pub.json -w "%{http_code}" -X POST "$B/accounts/$ACCT/publish" -H "Content-Type: application/json" -d "{\"video_asset_id\":$VID,\"caption\":\"gm\"}")
  info "POST /publish → HTTP $RC · $(cat /tmp/pub.json | jqget "d.get('detail') or ('dispatch '+str(d.get('id'))+' status '+str(d.get('status')))")"
  ok "422=AiToEarn 未配(诚实边界);配好 AiToEarn + autopilot 后此步自动真发"
fi

c "⑥⑦⑧⑨ 追踪 → 复盘 → 评估 → 改进(自我修正闭环)"
info "再跑一轮 Loop,看真实表现如何反馈…"
curl -s --max-time 60 -X POST "$B/accounts/$ACCT/loop" >/dev/null
curl -s "$B/accounts/$ACCT" | $PY -c "import sys,json
d=json.load(sys.stdin)
run=d['loop_runs'][-1] if d['loop_runs'] else None
if run:
    ev=run.get('evaluation') or {}
    print('   账号评估复合分：', ev.get('composite_score'), ' 拆解：', ev.get('breakdown'))
    for r in run.get('recommendations',[]):
        print('   建议['+r['kind']+']：', (r['content'] or '')[:90])" 2>/dev/null
ok "评估 + 改进建议(含真实表现纠偏)已产出 → 喂下一轮选题/脚本 → 闭环"

c "飞轮总览(UI 首页同源数据)"
curl -s "$B/flywheel" | $PY -c "import sys,json
d=json.load(sys.stdin)
print('   状态：', '已暂停' if d['paused'] else '自转中', ' | 自动驾驶账号：', d['autopilot_accounts'], '/', len(d['accounts']), ' | 待审：', d['pending_review'])
print('   9 步计数：', {s['key']: s['count'] for s in d['steps']})" 2>/dev/null
c "演示完成 · 打开 http://127.0.0.1:5173/ 看飞轮转起来"
