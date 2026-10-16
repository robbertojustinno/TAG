"""Optional, tenant-owned certificate record and master report."""
import json
from decimal import Decimal, InvalidOperation
from io import BytesIO
from html import escape
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
    section('1. Dados do instrumento',[(label,getattr(item,key,None)) for key,label in [('tag','TAG'),('name','Descrição'),('equipment_type','Tipo'),('manufacturer','Fabricante'),('model','Modelo'),('serial_number','Número de série'),('sector','Departamento'),('location','Localização'),('calibration_date','Última calibração'),('next_calibration_date','Próxima calibração'),('status','Status')]])
    section('2. Dados metrológicos',[(label,getattr(item,key,None)) for key,label in [('measurand','Grandeza'),('measurement_unit','Unidade'),('range_min','Faixa mínima'),('range_max','Faixa máxima'),('accuracy_class','Classe'),('resolution','Resolução'),('ema','EMA'),('reading_contribution','Contribuição da leitura')]])
    section('3. Certificado, método e condições',[(label,record.get(key)) for key,label in FIELDS.items()])
    for table,title in [('standards','4. Padrões e rastreabilidade'),('results','5. Resultados por ponto')]:
        story.append(Paragraph(title,styles['Heading2']))
        # Narrow, repeated groups avoid illegible eleven-column tables on A4.
        for index,row in enumerate(record.get(table,[]),1):
            if table == 'results':
                computed = evaluate_points(item, record)[index-1]
                row = {**row, 'calculated_error': computed['error'], 'acceptance': computed['acceptance']}
            columns = {**TABLES[table], **({'calculated_error':'Erro calculado (indicação - referência)', 'acceptance':'Avaliação: |erro| <= EMA (sem incerteza)'} if table == 'results' else {})}
            section(('Padrão ' if table=='standards' else 'Ponto ')+str(index),[(label,row.get(key)) for key,label in columns.items()])
        if not record.get(table): story.append(para('Não informado'))
    section('6. Notas do cadastro',[('Notas',item.notes)])
    def footer(c,doc):
        c.setFont('Helvetica',8);c.drawString(15*mm,10*mm,'TAGCheck | '+item.tag);c.drawRightString(195*mm,10*mm,'Página '+str(doc.page))
    SimpleDocTemplate(buf,pagesize=A4,leftMargin=15*mm,rightMargin=15*mm,topMargin=15*mm,bottomMargin=18*mm).build(story,onFirstPage=footer,onLaterPages=footer)
    buf.seek(0);return buf
