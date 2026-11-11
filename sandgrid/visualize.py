"""Offline HTML and GIF animation for the continuous-flow sand gate model.

HTML contains an opening frame and one frame per *actual* transfer event;
this shows automatically activated gates, even within a single paid action.
GIF is a compact one-frame-per-action summary for compatibility with
existing save_gif() callers and tests.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from .model import SandGrid


def _gate_data(model: SandGrid) -> list[dict]:
    result = []
    for action in model.actions:
        bit = model.gate_bit(action.id)
        if bit is not None:
            result.append(dict(bit=bit, kind=action.kind, src=action.src,
                               dst=action.dst, action_id=action.id))
    return result


def _timeline(model: SandGrid, initial: int, actions: list[int]) -> tuple[list[dict], list[dict]]:
    """Reconstruct intermediate occupancies/masks from trace flow_events.

    The final result is checked against the model after *every* action, so
    a graphics/model disagreement fails instead of silently drawing fiction.
    """
    trace = model.trace(initial, actions)
    occ, mask = model.decode(initial)
    frames = [dict(step=0, stage='initial', occupancy=occ.copy(), mask=mask,
                   cost=0, total=0, label='Initial grid', selected=None,
                   event=None, blocked=False)]
    for k, step in enumerate(trace[1:], 1):
        action_id = step['action']
        action = model.actions[action_id]
        bit = model.gate_bit(action_id)
        if bit is not None:
            if mask & (1 << bit):
                raise AssertionError(f'action {action_id} opens an already-open gate')
            mask |= 1 << bit
        events = step.get('flow_events', [])
        frames.append(dict(step=k, stage='opening', occupancy=occ.copy(),
                           mask=mask, cost=step['step_cost'],
                           total=step['total_cost'], label=action.label,
                           selected={'kind': action.kind, 'src': action.src,
                                     'dst': action.dst, 'gate_bit': bit},
                           event=None, blocked=(len(events) == 0)))
        for ev in events:
            delta = int(round(ev['amount'] * 2))
            if delta < 1 or delta > 2:
                raise AssertionError('unexpected transfer amount')
            src, dst = ev['src'], ev['dst']
            occ[src] -= delta
            if dst is not None:
                occ[dst] += delta
            gate_bit = ev['gate_bit']
            if gate_bit is not None and ev.get('gate_closed', False):
                mask &= ~(1 << gate_bit)
            frames.append(dict(step=k, stage='flow', occupancy=occ.copy(), mask=mask,
                               cost=step['step_cost'], total=step['total_cost'],
                               label=action.label, selected=None, event=ev,
                               blocked=False))
        closed = step.get('closed_gate_bits', [])
        if closed:
            for gate_bit in closed:
                mask &= ~(1 << gate_bit)
            frames.append(dict(step=k, stage='settled', occupancy=occ.copy(),
                               mask=mask, cost=step['step_cost'],
                               total=step['total_cost'], label=action.label,
                               selected=None, event=None, blocked=False,
                               closed_gates=closed))
        if not any(occ) and mask:
            mask = 0
            frames.append(dict(step=k, stage='complete', occupancy=occ.copy(),
                               mask=0, cost=step['step_cost'],
                               total=step['total_cost'], label='All sand removed',
                               selected=None, event=None, blocked=False))
        expected_occ, expected_mask = model.decode(step['state'])
        if occ != expected_occ or mask != expected_mask:
            raise AssertionError(
                f'animation and model disagree at step {k}: '
                f'{(occ,mask)} != {(expected_occ,expected_mask)}')
    return trace, frames


def save_html(model: SandGrid, initial: int, actions: list[int], filename: str | Path,
              title: str = 'Sand Grid Solution') -> Path:
    _, frames = _timeline(model, initial, actions)
    payload = json.dumps(dict(rows=model.rows, cols=model.cols,
                              gates=_gate_data(model), frames=frames),
                         ensure_ascii=False).replace('</', '<\\/')
    page = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{color-scheme:light;font-family:system-ui,-apple-system,sans-serif;color:#203047;background:#f3f6fa}
body{max-width:920px;margin:0 auto;padding:20px}h1{font-size:1.5rem;margin:0 0 6px}
.sub{color:#536780;font-size:.92rem}.panel{background:#fff;border:1px solid #d5dfeb;border-radius:14px;padding:18px;margin-top:16px}
canvas{display:block;width:100%;max-width:680px;margin:auto;background:#fdfefe;border-radius:8px}
.controls{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin:16px 0}
button,select{background:#f2f5f9;border:1px solid #b9c8db;border-radius:7px;padding:8px 12px;color:#203047;cursor:pointer}
button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid #3982d2}
#seek{flex:1;min-width:130px;accent-color:#3468a7}
.info{display:flex;flex-wrap:wrap;gap:9px}.info span{border:1px solid #dee5ef;background:#f9fbff;border-radius:7px;padding:7px 9px}
#description{font-weight:600;margin:15px 0 7px;min-height:1.5em}
#eventDetail{font-size:.93rem;min-height:1.5em;color:#3a5872}
.legend{font-size:.87rem;color:#536780;line-height:1.6;margin:12px 0 0}
</style></head><body><h1>__TITLE__</h1>
<div class="sub">Cell labels use assignment values: 1 = full, 0.5 = half, 0 = empty. Every gate opening costs one action; automatic flows do not create extra actions.</div>
<div class="panel"><canvas id="grid" aria-label="Sand transfer and gate status animation"></canvas>
<div class="controls"><button id="prev">◀ Previous</button><button id="play">▶ Play</button><button id="next">Next ▶</button>
<label for="speed">Speed</label><select id="speed"><option value="1800">Slow</option><option value="950" selected>Normal</option><option value="360">Fast</option></select></div>
<div class="controls"><span id="progress"></span><input id="seek" type="range" min="0" value="0" aria-label="Animation timeline"></div>
<div class="info"><span id="stepCost"></span><span id="totalCost"></span><span id="remaining"></span></div>
<div id="description"></div><div id="eventDetail"></div>
<p class="legend">Purple: gate currently open (vertical or directed horizontal). Orange: selected gate opening. Green: direct sand transfer. Blue: automatic transfer through a previously open gate. Red dot: gate closes after transfer. Downward gates close when the upstream source empties; blocked gates stay purple.</p>
</div><script>
const data=__DATA__, frames=data.frames, gates=data.gates, cols=data.cols, rows=data.rows;
const canvas=document.getElementById('grid'),ctx=canvas.getContext('2d');
const CELL=Math.max(52,Math.min(92,650/cols,520/rows)), PAD=42;
canvas.width=2*PAD+cols*CELL; canvas.height=2*PAD+rows*CELL+25;
let index=0,timer=null;const $=id=>document.getElementById(id);
$('seek').max=frames.length-1;
function center(i){return [PAD+(i%cols+.5)*CELL,PAD+(Math.floor(i/cols)+.5)*CELL]}
function arrow(x1,y1,x2,y2,color,width=3){
 const a=Math.atan2(y2-y1,x2-x1);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineCap='round';
 ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();
 ctx.beginPath();ctx.moveTo(x2,y2);ctx.lineTo(x2-10*Math.cos(a-.55),y2-10*Math.sin(a-.55));
 ctx.moveTo(x2,y2);ctx.lineTo(x2-10*Math.cos(a+.55),y2-10*Math.sin(a+.55));ctx.stroke();
}
function gateMark(g,color){
 const [sx,sy]=center(g.src),[dx,dy]=center(g.dst);
 ctx.strokeStyle=color;ctx.lineWidth=5;ctx.lineCap='round';ctx.beginPath();
 if(g.kind==='down'){let y=(sy+dy)/2;ctx.moveTo(sx-14,y);ctx.lineTo(sx+14,y)}
 else{let x=(sx+dx)/2,shift=sgn(dx-sx)*5;ctx.moveTo(x,sy-14+shift);ctx.lineTo(x,sy+14+shift)}
 ctx.stroke();
 if(g.kind==='side'){
  const x=(sx+dx)/2, y=sy+sgn(dx-sx)*5;
  arrow(x-5*sgn(dx-sx),y,x+6*sgn(dx-sx),y,color,2);
 }
}
function sgn(x){return x>=0?1:-1}
function flowArrow(event,color){
 const [sx,sy]=center(event.src);
 if(event.dst===null)arrow(sx,sy+CELL*.06,sx,sy+CELL*.70,color,4);
 else{const [dx,dy]=center(event.dst);arrow(sx+(dx-sx)*.20,sy+(dy-sy)*.20,
 dx-(dx-sx)*.20,dy-(dy-sy)*.20,color,4)}
 if(event.gate_bit!==null && event.gate_closed){
  const g=gates.find(x=>x.bit===event.gate_bit);
  if(g){const [gx,gy]=center(g.src),[hx,hy]=center(g.dst);
    ctx.fillStyle='#cd5548';ctx.beginPath();ctx.arc((gx+hx)/2,(gy+hy)/2,5,0,Math.PI*2);ctx.fill()}
 }
}
function draw(){const f=frames[index];ctx.clearRect(0,0,canvas.width,canvas.height);
 ctx.font='12px system-ui';ctx.textAlign='center';
 for(let c=0;c<cols;c++){ctx.fillStyle='#728197';ctx.fillText(String(c+1),PAD+(c+.5)*CELL,24)}
 for(let r=0;r<rows;r++){ctx.fillStyle='#728197';ctx.fillText(String(r+1),20,PAD+(r+.5)*CELL+4)}
 for(let r=0;r<rows;r++)for(let c=0;c<cols;c++){
 const i=r*cols+c,x=PAD+c*CELL,y=PAD+r*CELL,v=f.occupancy[i];
 ctx.fillStyle='#fcfdff';ctx.fillRect(x+3,y+3,CELL-6,CELL-6);
 if(v){let h=(CELL-8)*v/2;ctx.fillStyle=v===2?'#b9874e':'#d8b47b';ctx.fillRect(x+4,y+CELL-4-h,CELL-8,h)}
 ctx.strokeStyle='#526783';ctx.lineWidth=1.5;ctx.strokeRect(x+3,y+3,CELL-6,CELL-6);
 ctx.fillStyle='#1e374e';ctx.font=`${Math.max(12,Math.floor(CELL*.22))}px system-ui`;
 ctx.fillText(v===2?'1':v===1?'0.5':'0',x+CELL/2,y+CELL/2+5);
 }
 for(const g of gates)if((f.mask & (2**g.bit))!==0)gateMark(g,'#8154c5');
 if(f.stage==='opening'&&f.selected){
  const a=f.selected,[sx,sy]=center(a.src);
  if(a.dst===null)arrow(sx,sy+CELL*.06,sx,sy+CELL*.70,'#e47a29');
  else{const [dx,dy]=center(a.dst);arrow(sx+(dx-sx)*.18,sy+(dy-sy)*.18,
  dx-(dx-sx)*.18,dy-(dy-sy)*.18,'#e47a29')}
 }
 if(f.stage==='flow'&&f.event)flowArrow(f.event,f.event.automatic?'#2488c3':'#26966b');
 $('progress').textContent=`Frame ${index+1}/${frames.length} · Action ${f.step}`;
 $('seek').value=index;
 $('stepCost').textContent=`Action cost: ${f.cost}`;
 $('totalCost').textContent=`Total cost: ${f.total}`;
 $('remaining').textContent=`Remaining sand: ${f.occupancy.reduce((a,b)=>a+b,0)/2}`;
 $('description').textContent=f.label;
 if(f.stage==='initial')$('eventDetail').textContent='Initial state';
 else if(f.stage==='opening')$('eventDetail').textContent=f.blocked?
 'Gate opened; no sand passed, so it stays open.' : 'Gate opening selected; transfer follows.';
 else if(f.stage==='complete')$('eventDetail').textContent='Goal reached; any remaining gates cleared.';
 else if(f.stage==='settled')$('eventDetail').textContent='Continuous flow settled; gates with empty sources are now closed.';
 else $('eventDetail').textContent=`${f.event.automatic?'Automatic':'Direct'} ${f.event.kind} transfer: ${f.event.amount} unit(s) of sand; flow continues while possible.`;
}
function stop(){if(timer!==null){clearInterval(timer);timer=null}$('play').textContent='▶ Play'}
function go(i){index=Math.max(0,Math.min(frames.length-1,i));draw();if(index===frames.length-1)stop()}
function play(){if(timer!==null){stop();return}if(index===frames.length-1)index=0;draw();$('play').textContent='❚❚ Pause';timer=setInterval(()=>go(index+1),Number($('speed').value))}
$('prev').onclick=()=>{stop();go(index-1)};$('next').onclick=()=>{stop();go(index+1)};
$('play').onclick=play;$('seek').oninput=e=>{stop();go(Number(e.target.value))};
$('speed').onchange=()=>{if(timer!==null){stop();play()}};
window.onkeydown=e=>{if(e.key==='ArrowLeft')$('prev').click();if(e.key==='ArrowRight')$('next').click()};
draw();
</script></body></html>'''
    target = Path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page.replace('__TITLE__', html.escape(title))
                          .replace('__DATA__', payload), encoding='utf-8')
    return target


def save_gif(model: SandGrid, initial: int, actions: list[int], filename: str | Path,
             duration_ms: int = 900) -> Path:
    """One frame per paid action, with both gate types and true flow events.

    For animated opening/flow/closure substeps use save_html instead.
    """
    from PIL import Image, ImageDraw, ImageFont

    if duration_ms < 100:
        raise ValueError('duration_ms must be at least 100')
    trace, _ = _timeline(model, initial, actions)
    cell = min(96, max(54, 620 // model.cols))
    left, top, footer = 50, 76, 137
    width = 2 * left + model.cols * cell
    height = top + model.rows * cell + footer
    gates = _gate_data(model)
    font = ImageFont.load_default()
    images = []

    def point(i):
        return (left + (i % model.cols) * cell + cell // 2,
                top + (i // model.cols) * cell + cell // 2)

    def draw_arrow(draw, start, end, color, width=4):
        from math import atan2, cos, sin
        x1, y1 = start
        x2, y2 = end
        draw.line((x1, y1, x2, y2), fill=color, width=width)
        angle = atan2(y2 - y1, x2 - x1)
        draw.line((x2, y2, x2-9*cos(angle-.6), y2-9*sin(angle-.6)),
                  fill=color, width=width)
        draw.line((x2, y2, x2-9*cos(angle+.6), y2-9*sin(angle+.6)),
                  fill=color, width=width)

    for k, item in enumerate(trace):
        img = Image.new('RGB', (width, height), '#f7f9fd')
        draw = ImageDraw.Draw(img)
        occ, mask = model.decode(item['state'])
        draw.text((left, 12), f'SAND GRID   Step {k}/{len(trace)-1}',
                  fill='#1c334e', font=font)
        draw.text((left, 35), f'Action cost: {item["step_cost"]} | Total: {item["total_cost"]}',
                  fill='#2a405b', font=font)
        for r in range(model.rows):
            draw.text((15, top + r*cell + cell//2), str(r+1), fill='#526a85', font=font)
            for c in range(model.cols):
                i = r*model.cols+c
                x, y = left+c*cell, top+r*cell
                draw.rectangle((x+3, y+3, x+cell-3, y+cell-3),
                               fill='white', outline='#617a95', width=2)
                if occ[i]:
                    bottom = y+cell-4
                    h = int((cell-8)*occ[i]/2)
                    draw.rectangle((x+4, bottom-h, x+cell-4, bottom),
                                   fill='#b9874e' if occ[i] == 2 else '#d8b47b')
                # Display convention: 1=full, 0.5=half, 0=empty (not internal occupancy).
                text = ('0', '0.5', '1')[occ[i]]
                draw.text((x+cell//2-len(text)*3, y+cell//2-6),
                          text, fill='#1d334a', font=font)
        for c in range(model.cols):
            draw.text((left+c*cell+cell//2, top-23), str(c+1),
                      fill='#526a85', font=font)

        for g in gates:
            if mask & (1 << g['bit']):
                src, dst = point(g['src']), point(g['dst'])
                midx, midy = (src[0]+dst[0])//2, (src[1]+dst[1])//2
                if g['kind'] == 'down':
                    draw.line((midx-14, midy, midx+14, midy), fill='#8057c5', width=6)
                else:
                    shift = 5 if dst[0]>src[0] else -5
                    draw.line((midx, midy-15+shift, midx, midy+15+shift),
                              fill='#8057c5', width=6)

        if item['action'] is not None:
            action = model.actions[item['action']]
            for ev in item.get('flow_events', []):
                start = point(ev['src'])
                if ev['dst'] is None:
                    end = (start[0], start[1]+cell*.75)
                else:
                    end = point(ev['dst'])
                color = '#2488c3' if ev['automatic'] else '#26966b'
                draw_arrow(draw, start, end, color)
            if not item.get('flow_events'):
                start = point(action.src)
                end = (start[0], start[1]+cell*.7) if action.dst is None else point(action.dst)
                draw_arrow(draw, start, end, '#e47a29')
            label = action.label.encode('ascii','replace').decode('ascii')
        else:
            label = 'INITIAL GRID'
        draw.text((left, top + model.rows*cell+16), label,
                  fill='#1c334e', font=font)
        draw.text((left, top + model.rows*cell+44),
                  f'Remaining sand: {sum(occ)/2:g} full-box units',
                  fill='#2a405b', font=font)
        evs = item.get('flow_events', [])
        automatic = sum(e['automatic'] for e in evs)
        draw.text((left, top + model.rows*cell+67),
                  f'Transfers: {len(evs)} ({automatic} automatic)',
                  fill='#526a85', font=font)
        draw.text((left, top + model.rows*cell+90),
                  'Purple: open gates  Green: direct  Blue: automatic',
                  fill='#526a85', font=font)
        images.append(img)
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(path, save_all=True, append_images=images[1:],
                   duration=duration_ms, loop=0, optimize=False)
    return path
