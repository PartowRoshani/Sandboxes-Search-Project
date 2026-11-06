"""Create an entirely offline, interactive HTML animation of any solution."""
from __future__ import annotations

import html
import json
from pathlib import Path
from .model import SandGrid


def save_html(model: SandGrid, initial: int, actions: list[int], filename: str | Path,
              title: str = 'Sand Grid Solution') -> Path:
    trace = model.trace(initial, actions)
    frames = []
    for i, item in enumerate(trace):
        state = item['state']
        occ, gate_mask = model.decode(state)
        a = model.actions[item['action']] if item['action'] is not None else None
        frames.append(dict(step=i, occupancy=occ, gates=gate_mask,
                           cost=item['step_cost'], total=item['total_cost'],
                           label=a.label if a else 'Initial grid',
                           kind=a.kind if a else None,
                           src=a.src if a else None, dst=a.dst if a else None))
    payload = json.dumps({'rows': model.rows, 'cols': model.cols, 'frames': frames},
                         ensure_ascii=False).replace('</', '<\\/')
    page = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{color-scheme:light;background:#f4f7fc;color:#1a293b;font-family:system-ui,-apple-system,sans-serif}
body{max-width:900px;margin:auto;padding:22px} h1{font-size:1.45rem;margin-bottom:4px}
.hint{color:#67788d;font-size:.92rem;margin-top:0}
.panel{background:white;border:1px solid #dce4ed;border-radius:16px;padding:20px;box-shadow:0 6px 20px #20334e10}
canvas{display:block;max-width:100%;margin:auto;background:#fbfcff;border-radius:10px}
.controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:16px 0 8px}
button{padding:9px 15px;cursor:pointer;background:#f5f8fc;border:1px solid #c3cedb;border-radius:9px;color:#152f4c}
button:focus-visible{outline:3px solid #4286db} button:hover{background:#e7edf7}
input[type=range]{flex:1;min-width:100px;accent-color:#3267aa}
.meta{display:flex;gap:18px;flex-wrap:wrap;margin:12px 0;font-size:.94rem}
.stat{border:1px solid #e4eaf2;border-radius:8px;padding:7px 10px;background:#f9fbfe}
#description{font-weight:650;min-height:25px;margin:12px 0}
.legend{font-size:.88rem;color:#536277;margin-top:10px}
</style></head><body><h1>__TITLE__</h1>
<p class="hint">Interactive, offline replay. Full = dark sand, half = light sand, empty = white.</p>
<div class="panel"><canvas id="grid" aria-label="Animated sand-grid state"></canvas>
<div class="controls"><button id="prev" aria-label="Previous step">◀ Prev</button>
<button id="toggle">▶ Play</button><button id="next" aria-label="Next step">Next ▶</button>
<label for="speed">Speed</label><select id="speed" aria-label="Playback speed"><option value="1600">Slow</option><option value="850" selected>Normal</option><option value="350">Fast</option></select></div>
<div class="controls"><span id="progress">0/0</span><input id="seek" type="range" min="0" max="0" value="0" aria-label="Step slider"></div>
<div class="meta"><div class="stat" id="stepCost"></div><div class="stat" id="totalCost"></div><div class="stat" id="remaining"></div></div>
<div id="description"></div><div class="legend">Orange arrows indicate the chosen action. Purple lines show vertical doors that remain open. Cells show the physical amount of sand.</div>
</div><script>
const data=__DATA__; const frames=data.frames; const cols=data.cols,rows=data.rows;
const canvas=document.getElementById('grid'),ctx=canvas.getContext('2d');
const CELL=Math.max(48,Math.min(85,630/cols,500/rows)); const PAD=34;
canvas.width=2*PAD+cols*CELL;canvas.height=2*PAD+rows*CELL;
let index=0,timer=null;
const $=id=>document.getElementById(id);
$('seek').max=frames.length-1;
function arrow(x1,y1,x2,y2){ const a=Math.atan2(y2-y1,x2-x1);
 ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();
 ctx.beginPath();ctx.moveTo(x2,y2);ctx.lineTo(x2-12*Math.cos(a-.55),y2-12*Math.sin(a-.55));ctx.moveTo(x2,y2);ctx.lineTo(x2-12*Math.cos(a+.55),y2-12*Math.sin(a+.55));ctx.stroke();}
function draw(){const f=frames[index];ctx.clearRect(0,0,canvas.width,canvas.height);
 ctx.font='12px system-ui';ctx.textAlign='center';
 for(let c=0;c<cols;c++){ctx.fillStyle='#76849b';ctx.fillText(String(c+1),PAD+(c+.5)*CELL,19)}
 for(let r=0;r<rows;r++){ctx.fillStyle='#76849b';ctx.fillText(String(r+1),16,PAD+(r+.5)*CELL+4)}
 for(let r=0;r<rows;r++)for(let c=0;c<cols;c++){
 const i=r*cols+c,x=PAD+c*CELL,y=PAD+r*CELL,v=f.occupancy[i];
 ctx.fillStyle='#fdfefe';ctx.fillRect(x+3,y+3,CELL-6,CELL-6);
 if(v){const height=(CELL-8)*(v/2);ctx.fillStyle=v===2?'#b9874e':'#d6ae72';ctx.fillRect(x+4,y+CELL-4-height,CELL-8,height)}
 ctx.strokeStyle='#526783';ctx.lineWidth=1.5;ctx.strokeRect(x+3,y+3,CELL-6,CELL-6);
 ctx.fillStyle='#263e56';ctx.font=`${Math.max(12,Math.floor(CELL*.23))}px system-ui`;
 ctx.fillText(v===2?'1':v===1?'½':'0',x+CELL/2,y+CELL/2+5)
 }
 ctx.strokeStyle='#845acb';ctx.lineWidth=6;ctx.lineCap='round';
 for(let r=0;r<rows-1;r++)for(let c=0;c<cols;c++){
 const gate=r*cols+c;
 if(f.gates & (2**gate)){
 const x=PAD+(c+.5)*CELL,y=PAD+(r+1)*CELL;
 ctx.beginPath();ctx.moveTo(x-14,y);ctx.lineTo(x+14,y);ctx.stroke();}}
 if(f.kind){const sr=Math.floor(f.src/cols),sc=f.src%cols;
 const sx=PAD+(sc+.5)*CELL,sy=PAD+(sr+.5)*CELL;
 ctx.strokeStyle='#e56d28';ctx.lineWidth=3;
 if(f.kind==='side'){const dr=Math.floor(f.dst/cols),dc=f.dst%cols;
 arrow(sx,sy,PAD+(dc+.5)*CELL,PAD+(dr+.5)*CELL)}
 else{arrow(sx,sy+CELL*.1,sx,sy+CELL*.66)} }
 $('progress').textContent=`${index} / ${frames.length-1}`;
 $('seek').value=index;
 $('stepCost').textContent=`Action cost: ${f.cost}`;
 $('totalCost').textContent=`Total cost: ${f.total}`;
 $('remaining').textContent=`Remaining sand: ${f.occupancy.reduce((a,b)=>a+b,0)/2} full-box units`;
 $('description').textContent=f.label;
}
function stop(){if(timer!==null){clearInterval(timer);timer=null}$('toggle').textContent='▶ Play'}
function go(i){index=Math.max(0,Math.min(frames.length-1,i));draw();if(index===frames.length-1)stop()}
function play(){if(timer!==null){stop();return}if(index===frames.length-1)index=0;draw();$('toggle').textContent='❚❚ Pause';
 timer=setInterval(()=>go(index+1),Number($('speed').value))}
$('prev').onclick=()=>{stop();go(index-1)};
$('next').onclick=()=>{stop();go(index+1)};
$('toggle').onclick=play;
$('seek').oninput=e=>{stop();go(Number(e.target.value))};
$('speed').onchange=()=>{if(timer!==null){stop();play()}};
window.onkeydown=e=>{if(e.key==='ArrowLeft'){$('prev').click()}if(e.key==='ArrowRight'){$('next').click()}};
draw();
</script></body></html>'''
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page.replace('__TITLE__', html.escape(title)).replace('__DATA__', payload),
                    encoding='utf-8')
    return path


def save_gif(model: SandGrid, initial: int, actions: list[int], filename: str | Path,
             duration_ms: int = 900) -> Path:
    """Save a looping, self-contained animated GIF (requires Pillow).

    Each frame is one state after one paid action. A basic font bundled with
    Pillow is used; the output does not distribute any font files.
    """
    from PIL import Image, ImageDraw, ImageFont
    if duration_ms < 100:
        raise ValueError('duration_ms must be at least 100')
    trace = model.trace(initial, actions)
    cell = min(94, max(52, 620 // model.cols))
    left, top, footer = 48, 78, 110
    width = left * 2 + model.cols * cell
    height = top + model.rows * cell + footer
    font = ImageFont.load_default()
    images = []
    for index, step in enumerate(trace):
        img = Image.new('RGB', (width, height), '#f6f8fc')
        draw = ImageDraw.Draw(img)
        occ, mask = model.decode(step['state'])
        draw.text((left, 14), f'SAND GRID   Step {index}/{len(trace)-1}',
                  fill='#182d47', font=font)
        draw.text((left, 37), f'Action cost: {step["step_cost"]}  |  Total: {step["total_cost"]}',
                  fill='#283c59', font=font)
        for row in range(model.rows):
            draw.text((12, top+row*cell+cell//2), str(row+1), fill='#526a85', font=font)
            for col in range(model.cols):
                idx = row * model.cols + col
                x, y = left+col*cell, top+row*cell
                draw.rectangle((x+2,y+2,x+cell-2,y+cell-2), fill='white', outline='#668099', width=2)
                sand = occ[idx]
                if sand:
                    base = y+cell-4
                    h = int((cell-8)*sand/2)
                    draw.rectangle((x+4,base-h,x+cell-4,base),
                                   fill='#c49359' if sand==2 else '#d5b37c')
                draw.text((x+cell//2-5,y+cell//2-6),
                          ('0', '1/2', '1')[sand], fill='#193048', font=font)
        for col in range(model.cols):
            draw.text((left+col*cell+cell//2, top-24), str(col+1), fill='#526a85', font=font)
        for row in range(model.rows-1):
            for col in range(model.cols):
                i = row*model.cols+col
                if mask & (1 << i):
                    x=left+col*cell+cell//2
                    y=top+(row+1)*cell
                    draw.line((x-17,y,x+17,y),fill='#8556cf',width=7)
        if step['action'] is None:
            label='INITIAL GRID'
        else:
            a = model.actions[step['action']]
            label = a.label.encode('ascii','replace').decode('ascii')
            r,c=divmod(a.src,model.cols)
            x=left+c*cell+cell//2
            y=top+r*cell+cell//2
            if a.kind=='down':
                draw.line((x,y,x,y+cell//3), fill='#e76e25', width=5)
                draw.polygon([(x,y+cell//3+10),(x-9,y+cell//3-2),(x+9,y+cell//3-2)],
                             fill='#e76e25')
            else:
                _, dc=divmod(a.dst,model.cols)
                x2=left+dc*cell+cell//2
                draw.line((x,y,x2,y), fill='#e76e25', width=5)
                arrow_direction=1 if x2>x else -1
                draw.polygon([(x2,y),(x2-12*arrow_direction,y-8),
                              (x2-12*arrow_direction,y+8)], fill='#e76e25')
        draw.text((left,top+model.rows*cell+16),label,fill='#182d47',font=font)
        draw.text((left,top+model.rows*cell+43),
                  f'Remaining sand: {sum(occ)/2:g} full-box units',
                  fill='#283c59',font=font)
        draw.text((left,top+model.rows*cell+65),
                  'Purple: connected gates   Orange: action',
                  fill='#526a85',font=font)
        images.append(img)
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(path, save_all=True, append_images=images[1:],
                   duration=duration_ms, loop=0, optimize=True)
    return path
