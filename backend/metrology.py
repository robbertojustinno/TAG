"""Optional form values; omitted keys are preserved on update."""
from decimal import Decimal, InvalidOperation
from fastapi import Form, HTTPException, Request

LABELS = {
    "measurand": "Grandeza",
    "measurement_unit": "Unidade de medição",
    "range_min": "Faixa mínima",
    "range_max": "Faixa máxima",
    "accuracy_class": "Classe",
    "resolution": "Resolução",
    "ema": "EMA",
    "reading_contribution": "Contribuição estimada da leitura",
}
NUMERIC = ('range_min', 'range_max', 'resolution', 'ema', 'reading_contribution')

def decimal_value(value, field):
    try:
        result = Decimal(str(value).strip().replace(',', '.'))
        if not result.is_finite() or abs(result) >= Decimal('1e14') or result.as_tuple().exponent < -10:
            raise InvalidOperation
        if field in ('resolution', 'ema', 'reading_contribution', 'accuracy_class') and result < 0:
            raise InvalidOperation
        return result
    except (InvalidOperation, ValueError):
        raise HTTPException(422, detail=f'{LABELS[field]}: valor numérico inválido') from None

async def metrology_form(request: Request,
    measurand: str | None = Form(None),
    measurement_unit: str | None = Form(None),
    range_min: str | None = Form(None),
    range_max: str | None = Form(None),
    accuracy_class: str | None = Form(None),
    resolution: str | None = Form(None),
    ema: str | None = Form(None),
    reading_contribution: str | None = Form(None),
    calculate_ema: bool = Form(False),
):
    form = await request.form()
    values = {}
    for key in LABELS:
        if key in form:
            raw = str(form[key]).strip()
            if len(raw) > 200:
                raise HTTPException(422, detail=f'{LABELS[key]}: máximo de 200 caracteres')
            values[key] = (decimal_value(raw, key) if key in NUMERIC else raw) if raw else None
    values['_calculate_ema'] = calculate_ema
    return values

def apply_metrology(item, values):
    calculate = values.get('_calculate_ema', False)
    merged = {key: values.get(key, getattr(item, key, None)) for key in LABELS}
    low, high = merged['range_min'], merged['range_max']
    if low is not None and high is not None and high < low:
        raise HTTPException(422, detail='Faixa máxima deve ser maior ou igual à faixa mínima')
    updates = {key: value for key, value in values.items() if key in LABELS}
    if calculate:
        if low is None or high is None or not merged['accuracy_class']:
            raise HTTPException(422, detail='Informe faixa mínima, máxima e classe percentual para calcular EMA')
        accuracy = decimal_value(str(merged['accuracy_class']).rstrip('%').strip(), 'accuracy_class')
        updates['ema'] = decimal_value((high - low) * accuracy / 100, 'ema')
    for key, value in updates.items():
        setattr(item, key, value)

def serialize_metrology(item):
    return {key: float(getattr(item, key)) if key in NUMERIC and getattr(item, key) is not None
            else getattr(item, key) for key in LABELS}
