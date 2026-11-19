"""Optional, tenant-owned certificate record and master report."""
import json
from decimal import Decimal, InvalidOperation
from io import BytesIO
from html import escape
from datetime import date as Date
from pathlib import Path
import re
from fastapi import Request, HTTPException
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

FIELDS = {
 'document_type':'Tipo de documento', 'certificate_number':'Número do certificado / CIE',
 'issue_date':'Data de emissão', 'laboratory':'Laboratório emissor', 'requester':'Solicitante',
 'requester_address':'Endereço do solicitante', 'contractor':'Contratante', 'contractor_address':'Endereço do contratante',
 'asset_number':'Patrimônio', 'building':'Edifício', 'equipment_id':'ID do equipamento', 'document_id':'ID do documento',
 'frequency':'Frequência de calibração', 'sensor_id':'Identificação do sensor', 'sensor_type':'Tipo de sensor',
 'sensor_length':'Comprimento do sensor', 'sensor_diameter':'Diâmetro do sensor', 'compensation':'Compensação',
 'indication_range':'Faixa de indicação', 'division':'Valor de divisão', 'group_number':'Número do grupo',
 'group_name':'Nome do grupo', 'span_accuracy':'Exatidão do intervalo (%)', 'reading_accuracy':'Exatidão da leitura (%)',
 'declared_accuracy':'Exatidão declarada', 'plus_minus':'Mais / menos', 'input_range':'Faixa de entrada',
 'output_range':'Faixa de saída', 'procedure':'Procedimento / método', 'temperature':'Temperatura ambiente',
 'humidity':'Umidade relativa', 'stabilization':'Tempo de estabilização (com unidade)', 'readings':'Leituras por ponto',
 'evaluated_range':'Faixa avaliada', 'uncertainty_note':'Declaração de incerteza', 'observations':'Observações / falha constatada',
 'limitations':'Restrições e notas do certificado', 'gaps':'Pendências / dados não informados',
 'conclusion':'Conclusão / condição técnica', 'decision_rule':'Regra de decisão / critério de aceitação',
 'approved_by':'Responsável / signatário informado', 'approval_date':'Data da aprovação informada',
}
TABLES = {
 'standards': {'identification':'Padrão utilizado','serial':'Série','certificate':'Certificado','laboratory':'Laboratório','calibration_date':'Calibração','valid_until':'Validade'},
 'results': {'reference':'Referência / entrada','input_unit':'Unidade de entrada','indicated':'Indicação / saída','output_unit':'Unidade de saída','low':'Limite baixo','high':'Limite alto','error':'Erro declarado','uncertainty':'Incerteza expandida','k':'k','neff':'neff','immersion':'Imersão'},
}

ASSET_DETAILS = {
    'equipment_type': 'Tipo de instrumento',
    'model': 'Modelo',
    'serial_number': 'Nº Série',
    'notes': 'Notas do cadastro',
}
METROLOGY_FIELDS = {
    'measurand': 'Grandeza', 'measurement_unit': 'Unidade de medição',
    'range_min': 'Faixa mínima', 'range_max': 'Faixa máxima', 'accuracy_class': 'Classe',
    'resolution': 'Resolução', 'ema': 'EMA', 'reading_contribution': 'Contribuição estimada da leitura',
}


def validate_record(value):
    if not isinstance(value, dict) or set(value) - (set(FIELDS) | set(TABLES)):
        raise HTTPException(422, 'Registro de calibração inválido')
    result = {}
    for key, val in value.items():
        if key in FIELDS:
            if not isinstance(val, str) or len(val) > 12000:
                raise HTTPException(422, 'Campo do certificado inválido ou muito longo')
            result[key] = val.strip()
        else:
            if not isinstance(val, list) or len(val) > 100:
                raise HTTPException(422, 'Máximo de 100 linhas por tabela')
            result[key] = []
            for row in val:
                if not isinstance(row, dict) or set(row) - set(TABLES[key]):
                    raise HTTPException(422, 'Coluna de resultados inválida')
                if any(not isinstance(v, str) or len(v)>1000 for v in row.values()):
                    raise HTTPException(422, 'Valor de tabela inválido')
                result[key].append({k:v.strip() for k,v in row.items()})
    return result

async def calibration_form(request: Request):
    form = await request.form()
    if 'calibration_record' not in form:
        return None  # legacy clients preserve data
    raw = str(form['calibration_record'])
    if len(raw.encode()) > 200000:
        raise HTTPException(422, 'Registro de calibração muito grande')
    try:
        return validate_record(json.loads(raw or '{}'))
    except (ValueError, TypeError):
        raise HTTPException(422, 'JSON de calibração inválido') from None

def apply_record(item, record):
    if record is not None:
        item.calibration_record = json.dumps(record, ensure_ascii=False)

def read_record(item):
    return json.loads(item.calibration_record) if item.calibration_record else {}

def evaluate_points(item, record):
    def number(value):
        try:
            n = Decimal(str(value).strip().replace(',', '.'))
            return n if n.is_finite() else None
        except (InvalidOperation, ValueError):
            return None
    evaluated = []
    for row in record.get('results', []):
        ref, indication = number(row.get('reference')), number(row.get('indicated'))
        unit_in = row.get('input_unit', '').strip().casefold()
        unit_out = row.get('output_unit', '').strip().casefold()
        error = indication - ref if ref is not None and indication is not None and unit_in and unit_in == unit_out else None
        ema = number(item.ema)
        eligible = error is not None and ema is not None and ema >= 0 and str(item.measurement_unit or '').strip().casefold() == unit_out and record.get('document_type', '').strip().casefold() != 'carta de inspeção'
        evaluated.append({'error': str(error) if error is not None else 'Não calculado: informe números e unidades iguais',
                          'acceptance': ('Conforme' if abs(error) <= ema else 'Não conforme') if eligible else 'Não avaliado'})
    return evaluated

def master_pdf(item, company_name):
    record = read_record(item)
    buf = BytesIO()
    styles = getSampleStyleSheet()
    for key in ('BodyText','Normal'):
        styles[key].fontSize=8; styles[key].leading=11
    def para(value):
        return Paragraph(escape(str(value if value not in (None,'') else 'Não informado')).replace('\n','<br/>'),styles['BodyText'])
    story=[Paragraph('Relatório Mestre do Instrumento',styles['Title']),para(company_name),para('TAG: '+item.tag),para('Registro interno consolidado. Não substitui o certificado original. Assinatura digital não é gerada por este relatório.'),Spacer(1,4*mm)]
    def section(title, pairs):
        story.append(Paragraph(title,styles['Heading2']))
        rows=[[para(k),para(v)] for k,v in pairs]
        t=LongTable(rows,colWidths=[57*mm,123*mm],hAlign='LEFT',splitInRow=1)
        t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.35,colors.HexColor('#cfd6e0')),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#eef2f7')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.extend([t,Spacer(1,3*mm)])
    identification = {
        'tag': 'TAG', 'name': 'Descrição', 'manufacturer': 'Fabricante',
        'sector': 'Departamento', 'location': 'Localização', 'calibration_date': 'Última calibração',
        'next_calibration_date': 'Próxima calibração', 'status': 'Status', **ASSET_DETAILS,
        'photo': 'Foto do instrumento',
    }
    section('1. Dados do instrumento', [
        *((label, getattr(item, key, None)) for key, label in identification.items()),
        ('Unidade de trabalho', getattr(item.unit, 'name', '') if getattr(item, 'unit', None) else ''),
        ('Categoria', category_path(item)),
    ])
    section('2. Dados metrológicos', [(label, getattr(item, key, None)) for key, label in METROLOGY_FIELDS.items()])
    section('3. Certificado, método e condições',[(label,record.get(key)) for key,label in FIELDS.items()])
    evaluated = evaluate_points(item, record)
    for table,title in [('standards','4. Padrões e rastreabilidade'),('results','5. Resultados por ponto')]:
        story.append(Paragraph(title,styles['Heading2']))
        # Narrow, repeated groups avoid illegible eleven-column tables on A4.
        for index,row in enumerate(record.get(table,[]),1):
            if table == 'results':
                computed = evaluated[index-1]
                row = {**row, 'calculated_error': computed['error'], 'acceptance': computed['acceptance']}
            columns = {**TABLES[table], **({'calculated_error':'Erro calculado (indicação - referência)', 'acceptance':'Avaliação: |erro| <= EMA (sem incerteza)'} if table == 'results' else {})}
            section(('Padrão ' if table=='standards' else 'Ponto ')+str(index),[(label,row.get(key)) for key,label in columns.items()])
        if not record.get(table): story.append(para('Não informado'))
    def footer(c,doc):
        c.setFont('Helvetica',8);c.drawString(15*mm,10*mm,'TAGCheck | '+item.tag);c.drawRightString(195*mm,10*mm,'Página '+str(doc.page))
    SimpleDocTemplate(buf,pagesize=A4,leftMargin=15*mm,rightMargin=15*mm,topMargin=15*mm,bottomMargin=18*mm).build(story,onFirstPage=footer,onLaterPages=footer)
    buf.seek(0);return buf


def category_path(item):
    names = []
    category = getattr(item, 'category', None)
    while category is not None:
        names.append(category.name)
        category = category.parent
    return ' / '.join(reversed(names))


def master_html(item, company_name, unit_name='', language='pt'):
    """Fill the customer-supplied HTML without rebuilding its report layout."""
    source = (Path(__file__).parent / 'templates' / 'master_report.html').read_text(encoding='utf-8')
    record = read_record(item)
    # The platform supplies data directly. PDF import code and its CDN are unnecessary.
    source = re.sub(r'<script\b[^>]*>.*?</script>', '', source, flags=re.S | re.I)
    source = re.sub(r'<input id="file"[^>]*>', '', source)
    source = re.sub(r'<button class="secondary"[^>]*>.*?</button>', '', source, flags=re.S)
    source = re.sub(r'(<div class="hint">).*?(</div>)', r'\1Confira os dados preenchidos e use Salvar como PDF para imprimir este modelo.\2', source, flags=re.S)
    source = source.replace('<td>Comparação direta com padrão rastreável</td>', '<td id="procedure"></td>')
    if __package__:
        from .report_locale import translate_template, report_text
    else:
        from report_locale import translate_template, report_text
    # Only the empty template is translated. Instrument names, notes and other
    # company-owned values are inserted afterwards and remain exactly as stored.
    source = source.replace('<section class="section">\n        <h3>2. Método', '<!-- asset-details -->\n      <section class="section">\n        <h3>2. Método', 1)
    source = translate_template(source, language)
    source = source.replace('IMBEL – Indústria de Material Bélico do Brasil', escape(company_name))
    def text(value):
        return escape(str(value if value is not None else ''), quote=True)
    def fill(field, value):
        nonlocal source
        pattern = rf'(<(?P<tag>[a-z0-9]+)\b[^>]*\bid="{re.escape(field)}"[^>]*>).*?(</(?P=tag)>)'
        source = re.sub(pattern, lambda m: m.group(1) + text(value) + m.group(3), source, count=1, flags=re.S)
    def date(value):
        try:
            return Date.fromisoformat(str(value)).strftime('%m/%d/%Y' if language == 'en' else '%d/%m/%Y')
        except ValueError:
            return str(value or '')
    mapping = {
        'id':item.tag, 'desc':item.name, 'fab':item.manufacturer,
        'last':date(item.calibration_date), 'next':date(item.next_calibration_date),
        'dep':item.sector, 'equip':record.get('equipment_id',''),
        'docid':record.get('document_id') or record.get('certificate_number',''),
        'loc':item.location, 'status':item.status, 'freq':record.get('frequency',''),
        'unit':unit_name, 'procedure':record.get('procedure',''),
        'temp':record.get('temperature',''), 'hum':record.get('humidity',''),
        'stab':record.get('stabilization',''), 'reads':record.get('readings',''),
        'range':record.get('evaluated_range') or record.get('input_range',''),
        'unc':record.get('uncertainty_note',''),
        'obs':record.get('observations',''),
        'gaps':record.get('gaps',''), 'approved':record.get('approved_by',''),
        'approvedDate':date(record.get('approval_date','')),
        'certno':'Nº ' + (record.get('certificate_number') or item.tag),
        'origin':company_name,
    }
    if not mapping['range'] and item.range_min is not None and item.range_max is not None:
        mapping['range']=f'{item.range_min} a {item.range_max} {item.measurement_unit or ""}'
    standards = record.get('standards', [])
    missing=[label for field,label in [('procedure','Procedimento não informado'),('unc','Declaração de incerteza não informada')] if not mapping[field]]
    if not standards:
        missing.append('Padrão utilizado não informado')
    if not record.get('results'):
        missing.append('Leituras não informadas')
    if not mapping['gaps']:
        mapping['gaps']='\n'.join(report_text(value, language) for value in missing)
    for field,value in mapping.items():
        fill(field,value)
    def label(value):
        return text(report_text(value, language))

    def section(title, pairs):
        details = ''.join(
            f'<dt>{label(caption)}</dt><dd>{text(value)}</dd>'
            for caption, value in pairs
        )
        return f'<section class="section"><h3>{label(title)}</h3><dl class="details">{details}</dl></section>'

    def report_table(table, rows):
        columns = TABLES[table]
        headers = ''.join(f'<th scope="col">{label(caption)}</th>' for caption in columns.values())
        body = ''.join(
            '<tr>' + ''.join(f'<td>{text(row.get(key))}</td>' for key in columns) + '</tr>'
            for row in rows
        )
        return f'<table id="{table}"><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>'

    source = re.sub(r'(<section class="section" id="sectionStandard">.*?</h3>).*?(</section>)',
                    lambda m: m[1] + report_table('standards', standards) + m[2], source, count=1, flags=re.S)
    results = []
    for stored in record.get('results', []):
        row = dict(stored)
        try:
            indication = Decimal(row.get('indicated', '').replace(',', '.'))
            ema = Decimal(str(item.ema).replace(',', '.'))
            measurement_unit = str(item.measurement_unit or '').strip().casefold()
            if (measurement_unit and row.get('output_unit', '').strip().casefold() == measurement_unit
                    and indication.is_finite() and ema.is_finite() and ema >= 0):
                row['low'] = row.get('low') or str(indication - ema)
                row['high'] = row.get('high') or str(indication + ema)
        except InvalidOperation:
            pass
        results.append(row)
    source = re.sub(r'<table id="results">.*?</table>',
                    lambda _: report_table('results', results), source, count=1, flags=re.S)

    asset = section('Dados complementares do instrumento', [
        *((caption, getattr(item, key, None)) for key, caption in ASSET_DETAILS.items()),
        ('Categoria', category_path(item)),
    ])
    photo_url = getattr(item, 'photo', '')
    if photo_url and photo_url.startswith(('https://', 'http://')):
        photo_label = label('Foto do instrumento')
        asset += (f'<figure class="instrument-photo"><figcaption>{photo_label}</figcaption>'
                  f'<a href="{text(photo_url)}"><img src="{text(photo_url)}" alt="{photo_label}"></a></figure>')
    metrology = section('Dados metrológicos', [
        (caption, getattr(item, key, None)) for key, caption in METROLOGY_FIELDS.items()
    ])
    existing_fields = {'equipment_id', 'document_id', 'frequency', 'procedure', 'temperature',
                       'humidity', 'stabilization', 'readings', 'evaluated_range', 'uncertainty_note',
                       'observations', 'gaps', 'approved_by', 'approval_date'}
    certificate = section('Dados complementares do certificado', [
        (caption, date(record.get(key)) if key == 'issue_date' else record.get(key))
        for key, caption in FIELDS.items() if key not in existing_fields
    ])
    source = source.replace('<!-- asset-details -->', asset + metrology, 1)
    last_footer = source.rindex('<footer class="footer">')
    source = source[:last_footer] + certificate + source[last_footer:]
    return source.replace('</head>', """
<style>
  .page { height: auto; overflow: visible; }
  .footer { position: static; margin-top: 12px; }
  .footer div:last-child { visibility: hidden; }
  .movable-section { break-inside: auto; page-break-inside: auto; }
  .section h3 { break-after: avoid; }
  .details { margin: 0; font-size: 11px; }
  .details dt { padding: 5px 7px; background: #f8fafc; font-weight: bold; break-after: avoid; }
  .details dd { margin: 0; padding: 5px 7px; min-height: 22px; border-bottom: 1px solid var(--line); }
  .details dd, .note { white-space: pre-wrap; overflow-wrap: anywhere; }
  th, td { overflow-wrap: anywhere; }
  .instrument-photo { margin: 12px 0; break-inside: avoid; }
  .instrument-photo img { display: block; max-width: 100%; max-height: 55mm; }
  @media print {
    @page { margin: 11mm; }
    .page { width: auto; height: auto; min-height: 0; padding: 0; }
    .footer { break-inside: avoid; }
  }
</style></head>""", 1)
