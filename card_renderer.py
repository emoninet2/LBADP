"""Configurable card layout; blank metadata is never rendered."""
import io
import json
from datetime import date
from PIL import Image, ImageDraw, ImageFont, ImageColor
import matplotlib.pyplot as plt


SIZE_PRESETS = {
    'square': (1080, 1080),
    'portrait': (1080, 1350),
    'story': (1080, 1920),
    'landscape': (1920, 1080),
    'wide': (1200, 630),
}


def canvas_size(config):
    canvas = config.get('canvas', {})
    preset = canvas.get('preset', 'custom' if 'width' in canvas or 'height' in canvas else 'portrait')
    # Named presets select a size; custom (or dimensions alone) uses width/height.
    if preset == 'custom':
        size = (canvas.get('width'), canvas.get('height'))
        if any(type(v) is not int or not 600 <= v <= 4096 for v in size):
            raise ValueError('Custom width and height must be integers from 600 to 4096 pixels')
        if not 0.5 <= size[0] / size[1] <= 2.0:
            raise ValueError('Custom aspect ratio must be between 1:2 and 2:1')
        return size
    if preset not in SIZE_PRESETS:
        raise ValueError(f'Unknown canvas preset {preset!r}. Choose {", ".join(SIZE_PRESETS)}, or custom')
    return SIZE_PRESETS[preset]


def load_config(path):
    with open(path, encoding='utf-8') as f:
        config = json.load(f)
    if not isinstance(config, dict):
        raise ValueError('Card config must be a JSON object')
    for group in ('sections', 'fields', 'chart'):
        values = config.get(group, {})
        if not isinstance(values, dict) or any(type(v) is not bool for v in values.values()):
            raise ValueError(f'{group} must contain true/false settings')
    canvas_size(config)
    return config


def font(size, bold=False):
    for name in ['DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf', 'Arial.ttf']:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def present(value):
    return value is not None and str(value).strip() != ''


def wrap_text(text, width, text_font):
    # Character-based wrapping also handles long equipment names without spaces.
    lines = []
    for paragraph in str(text).split('\n'):
        line = ''
        for char in paragraph:
            if line and text_font.getlength(line + char) > width:
                split = line.rfind(' ')
                if split > 0:
                    lines.append(line[:split])
                    line = line[split + 1:] + char
                else:
                    lines.append(line)
                    line = char
            else:
                line += char
        lines.append(line)
    return lines


def render_card(jump, speeds, phases, config, output_path):
    rgb = ImageColor.getrgb(config.get('background', '#0f172a'))
    if len(rgb) != 3:
        raise ValueError('Background must be an opaque RGB color')
    background = '#%02x%02x%02x' % rgb
    dark = sum(c*w for c, w in zip(rgb, (.2126, .7152, .0722))) < 150
    def blend(amount):
        return '#%02x%02x%02x' % tuple(round(c + ((255 if dark else 0)-c)*amount) for c in rgb)
    surface, border = blend(.055), blend(.16)
    text, muted = ('#f8fafc', '#94a3b8') if dark else ('#0f172a', '#475569')
    blue, orange, green = ('#38bdf8', '#fb923c', '#4ade80') if dark else ('#0369a1', '#c2410c', '#15803d')
    def enabled(group, key):
        return config.get(group, {}).get(key, True)
    def metric(key, label, transform=str):
        value = jump.get(key)
        return (label, transform(value)) if enabled('fields', key) and present(value) else None
    speed = lambda value: f'{float(value)*1.609344:.1f} km/h'
    altitude = lambda value: f'{value:,} ft'
    duration = phases.get('canopy_duration_sec')
    canopy_time = None
    if duration is not None and enabled('fields', 'canopyDuration'):
        seconds = round(duration)
        canopy_time = ('DURATION (EST.)', f'~{seconds//60}m {seconds%60:02d}s')
    blocks = []
    # Lead with date, time and jump type, followed by location and aircraft.
    # Context is slightly quieter than the main flight metrics.
    date_value = None
    if all(present(jump.get(k)) for k in ('year', 'month', 'date')):
        date_value = date(int(jump['year']), int(jump['month']), int(jump['date'])).strftime('%d %b %Y')
    time_value = None
    if all(present(jump.get(k)) for k in ('hour', 'minute')):
        time_value = f"{int(jump['hour']):02d}:{int(jump['minute']):02d}"
    overview_rows = []
    timing = []
    if enabled('fields', 'jumpDate') and date_value:
        timing.append(('DATE', date_value))
    if enabled('fields', 'jumpTime') and time_value:
        timing.append(('TIME', time_value))
    if enabled('sections', 'metadata'):
        jump_type = metric('jumpType', 'JUMP TYPE')
        if jump_type:
            timing.append(jump_type)
        n_way = metric('nWay', 'N-WAY', lambda v: f'{v}-way')
        if n_way:
            timing.append(n_way)
    if timing:
        overview_rows.append(timing)
    if enabled('sections', 'metadata'):
        location = [metric('dropzone', 'DROPZONE'), metric('country', 'COUNTRY'), metric('aircraft', 'AIRCRAFT')]
        location = [item for item in location if item]
        if location:
            overview_rows.append(location)
    if enabled('sections', 'jumpDetails') and overview_rows:
        layout_rows = []
        for row in overview_rows:
            width = 960 / len(row)
            entries = [(label, wrap_text(value, width - 56, font(29, True))) for label, value in row]
            row_height = 36 + max(len(lines) for _, lines in entries) * 36 + 18
            layout_rows.append((entries, row_height))
        blocks.append(('overview', 'JUMP DETAILS', blue, layout_rows, 65 + sum(h for _, h in layout_rows)))
    for key, title, color, values in [
        ('altitudes', 'ALTITUDES', blue, [metric('exitAltitude(feet)', 'EXIT', altitude), metric('depAltitude(feet)', 'DEPLOYMENT', altitude)]),
        ('freefall', 'FREEFALL', orange, [metric('freeFallTime(sec)', 'DURATION', lambda v:f'{v} sec'), metric('avgFreeFallTas(mph)', 'AVERAGE TAS', speed), metric('maxFreeFallTas(mph)', 'MAXIMUM TAS', speed)]),
        ('canopy', 'CANOPY', green, [canopy_time, metric('avgCanopyTas(mph)', 'AVERAGE TAS', speed), metric('maxCanopyTas(mph)', 'MAXIMUM TAS', speed)]),
    ]:
        values = [v for v in values if v]
        if enabled('sections', key) and values:
            blocks.append(('metrics', title, color, values, 160))
    if enabled('sections', 'metadata'):
        for title, definitions in [
            ('CONDITIONS', [('weather','WEATHER','')]),
            ('LANDING', [('landingDistanceFromTarget(m)','DISTANCE FROM TARGET',' m')]),
            ('EQUIPMENT', [('canopy','CANOPY',''),('canopySize','CANOPY SIZE',' sq ft'),('rig','RIG',''),('exitWeight(kg)','EXIT WEIGHT',' kg'),('equipmentNotes','EQUIPMENT NOTES','')]),
            ('VERIFICATION', [('verifierName','VERIFIER',''),('verifierCredentialType','CREDENTIAL TYPE',''),('verifierCredentialNumber','CREDENTIAL NUMBER',''),('verifyingSignature','SIGNATURE RECORD','')]),
            ('NOTES', [('notes','NOTES','')]),
        ]:
            entries=[]
            for key,label,suffix in definitions:
                if enabled('fields', key) and present(jump.get(key)):
                    lines=wrap_text(str(jump[key])+suffix, 900, font(25))
                    entries.append((label,lines))
            if entries:
                height=68+sum(30+len(lines)*33+18 for _,lines in entries)
                blocks.append(('metadata',title,blue,entries,height))
    chart_image=None
    show_alt=enabled('chart','altitude')
    show_speed=enabled('chart','speed')
    if enabled('sections','chart') and (show_alt or show_speed):
        fig, ax=plt.subplots(figsize=(8.5,2.4) if canvas_size(config)[0] < canvas_size(config)[1] else (6.0,3.8),facecolor=surface)
        ax.set_facecolor(background)
        ax.set_xlabel('Time (sec)',color=muted)
        ax.tick_params(colors=muted)
        ax.grid(True,linestyle='--',alpha=.15,color=text)
        axes=[ax]
        if show_alt:
            ax.plot(speeds['time_sec'],jump.get('data(feet)',[])[:len(speeds['time_sec'])],color=blue,linewidth=2.5)
            ax.set_ylabel('Altitude (ft)',color=blue)
        speed_ax=ax.twinx() if show_alt and show_speed else ax
        if speed_ax is not ax:
            axes.append(speed_ax)
        if show_speed:
            speed_ax.plot(speeds['time_sec'],speeds['jumptrack_speed'],color=orange,linewidth=2.5)
            speed_ax.set_ylabel('Speed (km/h)',color=orange)
            speed_ax.tick_params(colors=muted)
        deploy=phases.get('deployment_sec')
        if enabled('chart','deploymentMarker') and deploy is not None:
            ax.axvline(deploy,color=green,linestyle='--',linewidth=1.5)
            ax.text(deploy+4,.97,f'Deployment | {deploy:g}s',transform=ax.get_xaxis_transform(),color=green,fontsize=9,va='top',bbox=dict(facecolor=background,edgecolor='none',alpha=.85))
        for axis in axes:
            for spine in axis.spines.values():
                spine.set_color(border)
        fig.tight_layout()
        with io.BytesIO() as buffer:
            fig.savefig(buffer,format='png',dpi=200,bbox_inches='tight',facecolor=surface)
            buffer.seek(0)
            with Image.open(buffer) as im:
                chart_image=im.resize((960,round(im.height*960/im.width)),Image.Resampling.LANCZOS).convert('RGB')
        plt.close(fig)
        blocks.append(('chart','FLIGHT PROFILE',blue,[],chart_image.height+52))
    # Reflow into columns for square/wide canvases; retain a single reading
    # column for portrait/story. Measure every text block before drawing.
    output_w, output_h = canvas_size(config)
    logical_w = 1600 if output_w / output_h > 1.3 else 1080
    logical_h = round(logical_w * output_h / output_w)
    columns = 2 if output_w / output_h >= .95 else 1
    margin, gap = 40, 20
    column_w = (logical_w - 2 * margin - gap * (columns - 1)) / columns

    def prepare(block, width, scale):
        kind, title, color, values, _ = block
        pad = round(22 * scale)
        label_font = font(max(14, round(17 * scale)), True)
        value_font = font(max(17, round((31 if kind == 'metrics' else 25) * scale)), True)
        rows = []
        if kind == 'overview':
            entries = [(label, ' '.join(lines)) for row, _ in values for label, lines in row]
        elif kind == 'metadata':
            entries = [(label, ' '.join(lines)) for label, lines in values]
        else:
            entries = values
        if kind == 'chart':
            return {'height': round(290 * scale + 45 * scale), 'rows': [], 'pad':pad}
        cells = 3 if width > 800 else 2
        if kind == 'metrics':
            cells = len(entries) if width > 650 else 1
        if title == 'NOTES':
            cells = 1
        cell_w = (width - pad * 2) / cells
        for start in range(0, len(entries), cells):
            row = []
            for label, value in entries[start:start + cells]:
                lines = wrap_text(str(value), cell_w - 18, value_font)
                label_lines = wrap_text(label, cell_w - 18, label_font)
                row.append((label_lines, lines))
            row_h = max(len(labels)*(label_font.size+5) + len(lines)*(value_font.size+7) for labels,lines in row) + round(15*scale)
            rows.append((row, row_h))
        height = round(53 * scale) + sum(h for _,h in rows) + pad
        return dict(height=height, rows=rows, pad=pad, cell_w=cell_w, label_font=label_font, value_font=value_font)

    # Try comfortable type first. Never crop or silently remove selected fields.
    placement = None
    for step in range(21):
        scale = 1 - step * .025
        header_h = round(160 * scale)
        bottom_h = (38 if enabled('sections','footnote') else 0) + (45 if enabled('sections','footer') else 0) + margin
        bottoms = [header_h] * columns
        candidate = []
        for block in blocks:
            # Put jump details across the top; remaining sections flow in columns.
            spanning = block[0] == 'overview'
            width = logical_w - 2 * margin if spanning else column_w
            layout = prepare(block, width, scale)
            if spanning:
                x, y = margin, max(bottoms)
                bottoms = [y + layout['height'] + gap] * columns
            else:
                col = min(range(columns), key=lambda i: bottoms[i])
                x, y = margin + col * (column_w + gap), bottoms[col]
                bottoms[col] = y + layout['height'] + gap
            candidate.append((block,x,y,width,layout))
        if max(bottoms) + bottom_h <= logical_h:
            placement = candidate
            break
    if placement is None:
        raise ValueError('Selected content does not fit this canvas legibly. Choose story or a taller custom size, shorten notes, or disable fields/sections in card_config.json. No image was overwritten.')
    card = Image.new('RGB',(logical_w,logical_h),background)
    draw = ImageDraw.Draw(card)
    draw.text((margin,22),'JUMP LOG',fill=blue,font=font(round(18*scale),True))
    draw.text((margin,round(48*scale)),f"Jump #{jump['jumpNumber']:02d}",fill=text,font=font(round(58*scale),True))
    for block,x,y,width,layout in placement:
        kind,title,color,values,_ = block
        h,pad=layout['height'],layout['pad']
        draw.rounded_rectangle((x,y,x+width,y+h),radius=16,fill=surface,outline=border)
        draw.text((x+pad,y+round(16*scale)),title,fill=color,font=font(max(15,round(19*scale)),True))
        row_y=y+round(53*scale)
        if kind=='chart':
            # Contain the plot with its original aspect ratio; never stretch it.
            available_w,available_h=round(width-2*pad),round(h-55*scale-pad)
            factor=min(available_w/chart_image.width,available_h/chart_image.height)
            plot=chart_image.resize((max(1,round(chart_image.width*factor)),max(1,round(chart_image.height*factor))),Image.Resampling.LANCZOS)
            card.paste(plot,(round(x+(width-plot.width)/2),round(row_y+(available_h-plot.height)/2)))
            continue
        for row,row_h in layout['rows']:
            for i,(labels,lines) in enumerate(row):
                cell_x=x+pad+i*layout['cell_w']
                text_y=row_y
                for line in labels:
                    draw.text((cell_x,text_y),line,fill=muted,font=layout['label_font'])
                    text_y+=layout['label_font'].size+5
                for line in lines:
                    draw.text((cell_x,text_y),line,fill=text,font=layout['value_font'])
                    text_y+=layout['value_font'].size+7
            row_y+=row_h
    footer_y=logical_h-bottom_h+10
    if enabled('sections','footnote'):
        draw.text((margin,footer_y),'TAS = true airspeed  /  Canopy time is estimated',fill=muted,font=font(16))
        footer_y+=38
    if enabled('sections','footer'):
        draw.line((margin,footer_y,logical_w-margin,footer_y),fill=border)
        draw.text((margin,footer_y+12),'LOGBOOK DATA PROCESSOR',fill=muted,font=font(15,True))
        draw.text((logical_w-margin,footer_y+12),'JumpTrack Analytics',fill=blue,font=font(16),anchor='ra')
    if card.size != (output_w,output_h):
        card=card.resize((output_w,output_h),Image.Resampling.LANCZOS)
    card.save(output_path,'PNG')
