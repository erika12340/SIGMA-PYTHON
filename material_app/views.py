from django.shortcuts import render
from material_app.models import MD_MATERIALS, MD_MACHINE_TYPES, MD_SEMI_FINISHED_CLASSES,TRC_BASIC_TABLE,  MD_BOM, DC_PRODUCTION_DATA, MD_WORKERS, WMS_TRACEABILITY, MD_PRODUCTION_PHASES, WMS_TRACEABILITY_CU, MD_SOURCES
from datetime import datetime, timedelta, time, date
from django.db.models import OuterRef, Subquery
from django.db.models.functions import TruncDate, ExtractHour
from django.db.models import OuterRef, Subquery, Q
from django.db.models import Sum, Count
from django.core.serializers.json import DjangoJSONEncoder
import json

def dashboard(request):
    # ===================== TRACEABILITY DASHBOARD =====================
    start_date_raw = request.GET.get('start_date')
    end_date_raw = request.GET.get('end_date')
    selected_pp = request.GET.get('trc_code')
    selected_mch_info = request.GET.get('mch_info')

    # ======= HELPER FUNCTIONS =========
    def parse_date_shift(raw_value):
        if not raw_value:
            return None, None
        try:
            date_part, shift_part = raw_value.split('|')
            return datetime.strptime(date_part, "%Y-%m-%d").date(), int(shift_part)
        except Exception:
            return None, None
 
    def get_shift_datetime_range(date_obj, shift_num):
        if shift_num == 1:
            return datetime.combine(date_obj, time(0,0,0)), datetime.combine(date_obj, time(8,0,0))
        elif shift_num == 2:
            return datetime.combine(date_obj, time(8,0,0)), datetime.combine(date_obj, time(16,0,0))
        elif shift_num == 3:
            return datetime.combine(date_obj, time(16,0,0)), datetime.combine(date_obj, time(23,59,59))
        return None, None

    def hour_to_shift(hour):
        if 0 <= hour < 8: return 1
        if 8 <= hour < 16: return 2
        return 3

    # ======= PARSE FILTER DATE & SHIFT =======
    start_date, start_shift = parse_date_shift(start_date_raw)
    end_date, end_shift = parse_date_shift(end_date_raw)

    start_dt, end_dt = None, None
    if start_date and start_shift:
        start_dt, _ = get_shift_datetime_range(start_date, start_shift)
    if end_date and end_shift:
        _, end_dt = get_shift_datetime_range(end_date, end_shift)

    # ======= DEFAULT KE HARI INI JIKA TIDAK DIPILIH =======
    if not start_dt or not end_dt:
        today = date.today()
        start_dt = datetime.combine(today, time(0,0,0))
        end_dt = datetime.combine(today, time(23,59,59))

    # ======= DROPDOWN TANGGAL & SHIFT =======
    date_shift_choices = []
    date_shift_raw_qs = (
        WMS_TRACEABILITY.objects
        .annotate(date=TruncDate('TRC_START_TIME'))
        .annotate(hour=ExtractHour('TRC_START_TIME'))
        .values('date','hour')
        .distinct()
        .order_by('-date','hour')
    )
    
    seen = set()
    for rec in date_shift_raw_qs:
        date_val, hour = rec.get('date'), rec.get('hour')
        if date_val is None or hour is None: continue
        shift = hour_to_shift(hour)
        key = (date_val, shift)
        if key in seen: continue
        seen.add(key)
        date_shift_choices.append({
            'value': f"{date_val.isoformat()}|{shift}",
            'label': f"{date_val.strftime('%d/%m/%Y')} - Shift {shift}"
        })

    # ======= DROPDOWN PP_CODE =======
    trc_list_qs = WMS_TRACEABILITY.objects.filter(TRC_START_TIME__range=(start_dt,end_dt))
    pp_desc_subquery = MD_PRODUCTION_PHASES.objects.filter(
        PP_CODE=OuterRef('TRC_PP_CODE')
    ).values('PP_DESC')[:1]

    trc_list = trc_list_qs.annotate(
        PP_DESC=Subquery(pp_desc_subquery)
    ).values('TRC_PP_CODE','PP_DESC').distinct().order_by('TRC_PP_CODE')

    # ======= DROPDOWN MESIN =======
    machines = []
    if selected_pp:
        machines_qs = WMS_TRACEABILITY.objects.filter(TRC_PP_CODE=selected_pp, TRC_START_TIME__range=(start_dt,end_dt))
        machines = machines_qs.values('TRC_PP_CODE','TRC_MCH_CODE').distinct().order_by('TRC_MCH_CODE')

    # ======= TOTAL CONSUMED & PRODUCED =======
    qs_filter = Q(TRC_START_TIME__range=(start_dt,end_dt))
    if selected_pp:
        qs_filter &= Q(TRC_PP_CODE=selected_pp)
    if selected_mch_info:
        parts = selected_mch_info.split('|')
        if len(parts) == 2:
            _, mch_code = parts
            qs_filter &= Q(TRC_MCH_CODE=mch_code)
        else:
            mch_code = None

    total_consumed = WMS_TRACEABILITY.objects.filter(TRC_FL_PHASE='C').filter(qs_filter).count()
    total_produced = WMS_TRACEABILITY.objects.filter(TRC_FL_PHASE='P').filter(qs_filter).count()


    # ========= JOIN MD_MATERIALS KE MD_SEMI_FINISHED_CLASSES =========
    materials = MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE'))

  
    # ======== DETAIL TABEL CONSUMED DAN PRODUCED (SUMMARY) =========
    consumed_summary = (
        WMS_TRACEABILITY.objects
        .filter(qs_filter, TRC_FL_PHASE='C')
        .annotate(
            SFC_CODE=Subquery(materials.values('SFC_CODE__SFC_CODE')[:1]),
            SFC_DESC=Subquery(materials.values('SFC_CODE__SFC_DESC')[:1]),
            MAT_CODE=Subquery(materials.values('MAT_CODE')[:1]),   
        )
        .values(
            'TRC_PP_CODE',
            'TRC_MAT_SAP_CODE',
            'MAT_CODE',      
            'SFC_CODE',
            'SFC_DESC',
        )
        .annotate(total=Count('*'))
        .order_by('-total', 'TRC_SO_CODE')
    )


    produced_summary = (
        WMS_TRACEABILITY.objects
        .filter(qs_filter, TRC_FL_PHASE='P')
        .annotate(
            SFC_CODE=Subquery(materials.values('SFC_CODE__SFC_CODE')[:1]),
            SFC_DESC=Subquery(materials.values('SFC_CODE__SFC_DESC')[:1]),
            MAT_CODE=Subquery(materials.values('MAT_CODE')[:1]),
        )
        .values(
            'TRC_PP_CODE',
            'TRC_MAT_SAP_CODE',
            'SFC_CODE',
            'MAT_CODE',
            'SFC_DESC',
        )
        .annotate(total=Count('*'))
        .order_by('-total', 'TRC_SO_CODE')
    )

    # ======== DETAIL ROWS (PER BARIS DATA) ========
    consumed_details = (
        WMS_TRACEABILITY.objects
        .filter(qs_filter, TRC_FL_PHASE='C')
        .annotate(
            SFC_CODE=Subquery(materials.values('SFC_CODE__SFC_CODE')[:1]),
            SFC_DESC=Subquery(materials.values('SFC_CODE__SFC_DESC')[:1]),
            MAT_CODE=Subquery(materials.values('MAT_CODE')[:1]),
        )
        .values(
            'TRC_PP_CODE',
            'TRC_MCH_CODE',
            'TRC_SO_CODE',
            'TRC_CU_EXT_PROGR',
            'MAT_CODE',
            'TRC_MAT_SAP_CODE',
            'TRC_MAT_VARIANT',
            'SFC_CODE',
            'SFC_DESC',
            'TRC_START_TIME',
            'TRC_END_TIME',
        )
        .order_by('-TRC_START_TIME')
    )

    produced_details = (
        WMS_TRACEABILITY.objects
        .filter(qs_filter, TRC_FL_PHASE='P')
        .annotate(
            SFC_CODE=Subquery(materials.values('SFC_CODE__SFC_CODE')[:1]),
            SFC_DESC=Subquery(materials.values('SFC_CODE__SFC_DESC')[:1]),
            MAT_CODE=Subquery(materials.values('MAT_CODE')[:1]),
        )
        .values(
            'TRC_PP_CODE',
            'TRC_MCH_CODE',
            'TRC_SO_CODE',
            'MAT_CODE', 
            'TRC_CU_EXT_PROGR',
            'TRC_MAT_SAP_CODE',
            'TRC_MAT_VARIANT',
            'SFC_CODE',
            'SFC_DESC',
            'TRC_START_TIME',
            'TRC_END_TIME',
        )
        .order_by('-TRC_START_TIME')
    )
























# ================= PRODUCTION DATA DASHBOARD =================
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    sfc_code = request.GET.get('sfc_code') or None
    mat_sap_code = request.GET.get('mat_sap_code') or None

    sfc_list = MD_SEMI_FINISHED_CLASSES.objects.filter(
        SFC_CODE__in=['AL', 'AX']
    ).order_by('SFC_CODE')

    daftar_mat_sap = []
    tabel_data = []
    total_quantity = 0

    start_dt = end_dt = None
    if start_date and end_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            pass

    if start_dt and end_dt:

        produksi_qs_base = DC_PRODUCTION_DATA.objects.filter(
            PS_DATE__date__range=(start_dt.date(), end_dt.date())
        )

        # =======================
        # FILTER SFC CODE
        # =======================
        if sfc_code and sfc_code.strip() != "":
            mat_codes_area = list(
                MD_MATERIALS.objects.filter(SFC_CODE=sfc_code)
                .values_list("MAT_SAP_CODE", flat=True)
            )

            if mat_codes_area:
                produksi_qs_base = produksi_qs_base.extra(
                    where=[
                        "MAT_SAP_CODE COLLATE SQL_Latin1_General_CP1_CI_AS IN (%s)" %
                        ",".join(["'%s'" % c for c in mat_codes_area])
                    ]
                )

        # =======================
        # DROPDOWN MAT_SAP_CODE
        # =======================
        prod_codes = list(
            produksi_qs_base.values_list("MAT_SAP_CODE", flat=True).distinct()
        )

        if prod_codes:
            daftar_mat_sap_qs = MD_MATERIALS.objects.extra(
                where=[
                    "MAT_SAP_CODE COLLATE SQL_Latin1_General_CP1_CI_AS IN (%s)" %
                    ",".join(["'%s'" % c for c in prod_codes])
                ]
            ).order_by("MAT_SAP_CODE")

            daftar_mat_sap = list(daftar_mat_sap_qs)

        # =======================
        # FILTER MAT_SAP_CODE
        # =======================
        if mat_sap_code and mat_sap_code.strip() != "":
            produksi_qs_base = produksi_qs_base.extra(
                where=[
                    "MAT_SAP_CODE COLLATE SQL_Latin1_General_CP1_CI_AS = %s"
                ],
                params=[mat_sap_code]
            )

        # =======================
        # DATA PRODUKSI
        # =======================
        produksi_qs = produksi_qs_base.values(
            "MAT_SAP_CODE", "MCH_CODE", "PS_START_PROD", "PS_END_PROD",
            "PS_DATE", "SHF_CODE", "PS_QUANTITY"
        ).order_by("PS_START_PROD")

        mat_codes = [row["MAT_SAP_CODE"] for row in produksi_qs]

        # =======================
        # MAP MATERIAL
        # =======================
        if mat_codes:
            mat_map = dict(
                MD_MATERIALS.objects.extra(
                    where=[
                        "MAT_SAP_CODE COLLATE SQL_Latin1_General_CP1_CI_AS IN (%s)" %
                        ",".join(["'%s'" % c for c in mat_codes])
                    ]
                ).values_list("MAT_SAP_CODE", "MAT_CODE")
            )

            sfc_map = dict(
                MD_MATERIALS.objects.extra(
                    where=[
                        "MAT_SAP_CODE COLLATE SQL_Latin1_General_CP1_CI_AS IN (%s)" %
                        ",".join(["'%s'" % c for c in mat_codes])
                    ]
                ).values_list("MAT_SAP_CODE", "SFC_CODE")
            )
        else:
            mat_map = {}
            sfc_map = {}

        sfc_desc_map = dict(
            MD_SEMI_FINISHED_CLASSES.objects.values_list("SFC_CODE", "SFC_DESC")
        )

        # =======================
        # GENERATE TABEL
        # =======================
        for row in produksi_qs:
            start = row["PS_START_PROD"]
            end = row["PS_END_PROD"]

            if isinstance(start, datetime) and isinstance(end, datetime):
                duration_sec = max((end - start).total_seconds(), 0)
                h = int(duration_sec // 3600)
                m = int((duration_sec % 3600) // 60)
                s = int(duration_sec % 60)
                durasi_hms = f"{h:02d}:{m:02d}:{s:02d}"
            else:
                durasi_hms = "00:00:00"

            tabel_data.append({
                "mat_code": mat_map.get(row["MAT_SAP_CODE"]),
                "mat_sap_code": row["MAT_SAP_CODE"],
                "mch_code": row["MCH_CODE"],
                "sfc_code": sfc_map.get(row["MAT_SAP_CODE"]),
                "sfc_desc": sfc_desc_map.get(sfc_map.get(row["MAT_SAP_CODE"]), ""),
                "ps_start_prod": start,
                "ps_end_prod": end,
                "ps_date": row["PS_DATE"],
                "durasi_hms": durasi_hms,
                "ps_quantity": int(row["PS_QUANTITY"] or 0),
                "shf_code": row["SHF_CODE"],
            })

        total_quantity = sum(int(r["ps_quantity"] or 0) for r in tabel_data)


    context = {
        'title': 'Dashboard Produksi',
        'sfc_list': sfc_list,
        'selected_sfc': sfc_code,
        'daftar_mat_sap': daftar_mat_sap,
        'selected_mat_sap': mat_sap_code,
        'selected_start_date': start_date,
        'selected_end_date': end_date,
        'tabel_data': tabel_data,
        'total_quantity': total_quantity,

        # Traceability tetap seperti sebelumnya
        'date_shift_choices': date_shift_choices,
        'selected_start_date': start_date_raw,
        'selected_end_date': end_date_raw,
        'trc_list': trc_list,
        'selected_pp': selected_pp,
        'machines': machines,
        'selected_mch_info': selected_mch_info,
        'total_consumed': total_consumed,
        'total_produced': total_produced,
        'consumed_details': consumed_details,
        'produced_details': produced_details,
        'consumed_summary': consumed_summary,
        'produced_summary': produced_summary,
    }

    return render(request,'templates2/dashboard.html',context)


















# ============ INFORMASI DETAIL IP MATERIALS  =============
def get_material_detail(mat_code):
    try:
        mat = MD_MATERIALS.objects.filter(MAT_CODE=mat_code).first()

        if not mat:
            return {}

        # MAT_OUT_MNG: jika 'F' atau None berarti ACTIVE, kalau 'T' berarti INACTIVE
        if mat.MAT_OUT_MNG in ['F', None]:
            status = 'ACTIVE'
        else:
            status = 'INACTIVE'

        return {
            'ip_code': mat.MAT_CODE,
            'spec': mat.MAT_SPEC_CODE,
            'mat_desc': mat.MAT_DESC,
            'status': status,
        }

    except Exception as e:
        print("[ERROR] Gagal mengambil detail material:", e)
        return {}

# =================== LINE MATERIALS ===================
def get_all_related_material_data(mat_sap_code, visited=None, level=0):
    if visited is None:
        visited = set()

    if mat_sap_code in visited:
        return []

    visited.add(mat_sap_code)
    data = []

    # MENCARI MAT_SAP_CODE
    child_boms = MD_BOM.objects.filter(MAT_SAP_CODE=mat_sap_code)

    if not child_boms.exists():
        
        mat = MD_MATERIALS.objects.filter(MAT_SAP_CODE=mat_sap_code).first()
        if mat:

            try:
                sfc_desc = mat.SFC_CODE.SFC_DESC
                sfc_code = mat.SFC_CODE.SFC_CODE

            except:
                sfc_desc = '-'
                sfc_code = '-'
            data.append({
                'level': level,
                'SFC_CODE': sfc_code,
                'SFC_DESC': sfc_desc,
                'BV_STATUS': '-',
                'MAT_CODE': mat.MAT_CODE,
                'MAT_SAP_CODE': mat.MAT_SAP_CODE,
                'CHILD_MAT_SAP_CODE': '-',
                'CNT_CODE': mat.CNT_CODE,
                'MAT_VARIANT': mat.MAT_VARIANT,
                'MAT_DESC': mat.MAT_DESC,
                'MAT_SPEC_CODE': mat.MAT_SPEC_CODE,
                'MT_CODE': '-',
                'MAT_MEASURE_UNIT': mat.MAT_MEASURE_UNIT,
                'BOM_QUANTITY': '-',
            })

    else:

        for bom in child_boms:
            child_code = bom.CHILD_MAT_SAP_CODE
            child_mat = MD_MATERIALS.objects.filter(MAT_SAP_CODE=child_code).first()
            if not child_mat:
                continue
            try:
                sfc_desc = child_mat.SFC_CODE.SFC_DESC
                sfc_code = child_mat.SFC_CODE.SFC_CODE
            except:
                sfc_desc = '-'
                sfc_code = '-'
            data.append({
                'level': level,
                'SFC_CODE': sfc_code,
                'SFC_DESC': sfc_desc,
                'BV_STATUS': bom.BV_STATUS,
                'MAT_CODE': child_mat.MAT_CODE,
                'MAT_SAP_CODE': mat_sap_code,
                'CHILD_MAT_SAP_CODE': child_code,
                'CNT_CODE': bom.CNT_CODE,
                'MAT_VARIANT': child_mat.MAT_VARIANT,
                'MAT_DESC': child_mat.MAT_DESC,
                'MT_CODE': bom.MT_CODE,
                'CHILD_CNT_CODE':bom.CHILD_CNT_CODE,
                'MAT_MEASURE_UNIT': child_mat.MAT_MEASURE_UNIT,
                'BOM_QUANTITY': bom.BOM_QUANTITY,
            })
            data += get_all_related_material_data(child_code, visited, level + 1)
    return data

# ================== MENU DAFTAR MATERIALS ==================
def daftar_materials(request):
    sfc_code = request.GET.get('sfc_code')
    mat_info = request.GET.get('mat_info')
    sfc_list = MD_SEMI_FINISHED_CLASSES.objects.all()
    materials = MD_MATERIALS.objects.filter(SFC_CODE=sfc_code) if sfc_code else []
    selected_mat_code = None
    selected_mat_info = mat_info
    material_detail = {}
    material_data = []

    if mat_info:

        try:
            mat_parts = mat_info.split('|')
            selected_mat_code = mat_parts[0]
            selected_mat_sap = mat_parts[1]
            material_detail = get_material_detail(selected_mat_code)
            material_data = get_all_related_material_data(selected_mat_sap)

        except Exception as e:
            print("[ERROR] Gagal menampilkan mat_info:", e)

    return render(request, 'daftar_materials.html', {
        'sfc_list': sfc_list,
        'materials': materials,
        'selected_sfc': sfc_code,
        'selected_mat_code': selected_mat_code,
        'selected_mat_info': selected_mat_info,
        'material_detail': material_detail,
        'material_data': material_data
    })







# =================== TRACEABILITY BY MACHINE ===================
def traceability_by_machine(request):
    trc_code = request.GET.get('trc_code')
    mch_info = request.GET.get('mch_info')
    start_date_raw = request.GET.get('start_date')
    end_date_raw = request.GET.get('end_date')
    trc_fl_phase = request.GET.get('trc_fl_phase')

    # === Fungsi bantu untuk parsing tanggal dan shift ===
    def parse_date_shift(raw_value):
        if not raw_value:
            return None, None
        try:
            date_part, shift_part = raw_value.split('|')
            date_obj = datetime.strptime(date_part, "%Y-%m-%d").date()
            shift_int = int(shift_part)
            return date_obj, shift_int
        except Exception:
            return None, None

    def get_shift_datetime_range(date_obj, shift_num):
        if shift_num == 1:
            return datetime.combine(date_obj, time(0, 0, 0)), datetime.combine(date_obj, time(8, 0, 0))
        elif shift_num == 2:
            return datetime.combine(date_obj, time(8, 0, 0)), datetime.combine(date_obj, time(16, 0, 0))
        elif shift_num == 3:
            return datetime.combine(date_obj, time(16, 0, 0)), datetime.combine(date_obj, time(23, 59, 59))
        return None, None

    def hour_to_shift(hour):
        if 0 <= hour < 8:
            return 1
        if 8 <= hour < 16:
            return 2
        return 3

    start_date, start_shift = parse_date_shift(start_date_raw)
    end_date, end_shift = parse_date_shift(end_date_raw)

    # === 1) Filter tanggal ke datetime range ===
    start_dt = end_dt = None
    if start_date and start_shift:
        start_dt, _ = get_shift_datetime_range(start_date, start_shift)
    if end_date and end_shift:
        _, end_dt = get_shift_datetime_range(end_date, end_shift)

    # === 2) Daftar tanggal|shift (seperti semula) ===
    date_shift_choices = []
    date_shift_raw_qs = (
        WMS_TRACEABILITY.objects
        .annotate(date=TruncDate('TRC_START_TIME'))
        .annotate(hour=ExtractHour('TRC_START_TIME'))
        .values('date', 'hour')
        .distinct()
        .order_by('-date', 'hour')
    )
    seen = set()
    for rec in date_shift_raw_qs:
        date = rec.get('date')
        hour = rec.get('hour')
        if date is None or hour is None:
            continue
        shift = hour_to_shift(hour)
        key = (date, shift)
        if key in seen:
            continue
        seen.add(key)
        label = f"{date.strftime('%d/%m/%Y')} - Shift {shift}"
        value = f"{date.isoformat()}|{shift}"
        date_shift_choices.append({'value': value, 'label': label})

    # === 3) Daftar PP_CODE (Production Phase) berdasarkan tanggal ===
    trc_list_qs = WMS_TRACEABILITY.objects.all()

    if start_dt and end_dt:
        trc_list_qs = trc_list_qs.filter(TRC_START_TIME__range=(start_dt, end_dt))

    pp_desc_subquery = MD_PRODUCTION_PHASES.objects.filter(
        PP_CODE=OuterRef('TRC_PP_CODE')
    ).values('PP_DESC')[:1]

    trc_list = (
        trc_list_qs
        .annotate(PP_DESC=Subquery(pp_desc_subquery))
        .values('TRC_PP_CODE', 'PP_DESC')
        .distinct()
        .order_by('TRC_PP_CODE')
    )

    # === 4) Daftar Mesin berdasarkan tanggal + PP_CODE ===
    machines = []
    if trc_code:
        machines_qs = WMS_TRACEABILITY.objects.filter(TRC_PP_CODE=trc_code)

        if start_dt and end_dt:
            machines_qs = machines_qs.filter(TRC_START_TIME__range=(start_dt, end_dt))

        machines = (
            machines_qs
            .values('TRC_PP_CODE', 'TRC_MCH_CODE')
            .distinct()
            .order_by('TRC_MCH_CODE')
        )

    # === 5) Daftar Phase ===
    phase_qs = WMS_TRACEABILITY.objects.all()
    if trc_code:
        phase_qs = phase_qs.filter(TRC_PP_CODE=trc_code)
        if trc_code == 'B02':
            phase_qs = phase_qs.exclude(TRC_FL_PHASE='P')
        elif trc_code == 'R01':
            phase_qs = phase_qs.exclude(TRC_FL_PHASE='C')
    phase = (
        phase_qs
        .values('TRC_FL_PHASE')
        .distinct()
        .order_by('TRC_FL_PHASE')
    )

    # === 6) Traceability Tree (biarkan logika lamanya) ===
    traceability_tree = []
    # 5) Build queryset hanya jika SEMUA form dipilih
    if trc_code and mch_info and start_date and end_date and trc_fl_phase:
        traceability_qs = WMS_TRACEABILITY.objects.all()

        # filter trc_code
        traceability_qs = traceability_qs.filter(TRC_PP_CODE=trc_code)

        # filter mesin
        try:
            trc_pp, trc_mch = mch_info.split('|')
            traceability_qs = traceability_qs.filter(TRC_PP_CODE=trc_pp, TRC_MCH_CODE=trc_mch)
        except ValueError:
            pass

        # Pengaturan tanggal (sql query)
        if start_shift and end_shift:
            start_dt, _ = get_shift_datetime_range(start_date, start_shift)
            _, end_dt = get_shift_datetime_range(end_date, end_shift)

            overlap_filter = (
                Q(TRC_END_TIME__gte=start_dt) & Q(TRC_START_TIME__lte=end_dt)
            ) | (
                Q(TRC_END_TIME__range=(start_dt, end_dt)) |
                Q(TRC_START_TIME__range=(start_dt, end_dt))
            )

            traceability_qs = traceability_qs.filter(overlap_filter)

        # Annotasi
        traceability_qs = traceability_qs.annotate(
            MAT_CODE=Subquery(
                MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')).values('MAT_CODE')[:1]
            ),
            WM_NAME=Subquery(
                MD_WORKERS.objects.filter(WM_CODE=OuterRef('TRC_WM_CODE')).values('WM_NAME')[:1]
            )
        )

        traceability_qs = traceability_qs.order_by('TRC_START_TIME')

        traceability_raw = list(traceability_qs.values(
            'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE', 'TRC_MAT_SAP_CODE',
            'TRC_WM_CODE', 'TRC_START_TIME', 'TRC_END_TIME', 'TRC_CU_EXT_PROGR',
            'TRC_FL_PHASE', 'MAT_CODE', 'WM_NAME'
        ))

        # --- Fungsi rekursif untuk child tree ---
        def get_child_cu_tree(parent_so, parent_cu, level=1):
            child_nodes = []
            parent_links = WMS_TRACEABILITY_CU.objects.filter(
                SO_CODE=parent_so,
                CU_EXT_PROGR=parent_cu
            )

            for link in parent_links:
                child_so = link.CHILD_SO_CODE
                child_cu = link.CHILD_CU_EXT_PROGR
                if not child_cu:
                    continue

                # ambil detail baris1
                detail1 = WMS_TRACEABILITY.objects.filter(
                    TRC_SO_CODE=child_so,
                    TRC_CU_EXT_PROGR=child_cu,
                    TRC_FL_PHASE='C'
                ).annotate(
                    MAT_CODE=Subquery(MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')).values('MAT_CODE')[:1]),
                    WM_NAME=Subquery(MD_WORKERS.objects.filter(WM_CODE=OuterRef('TRC_WM_CODE')).values('WM_NAME')[:1])
                ).values(
                    'TRC_PP_CODE','TRC_MCH_CODE','TRC_SO_CODE',
                    'TRC_MAT_SAP_CODE','TRC_WM_CODE','TRC_START_TIME',
                    'TRC_END_TIME','TRC_CU_EXT_PROGR','TRC_FL_PHASE','MAT_CODE','WM_NAME'
                ).first()

                # ambil detail baris2
                detail2 = None
                if detail1:
                    other_phase = 'P' if detail1['TRC_FL_PHASE'] == 'C' else 'C'
                    detail2 = WMS_TRACEABILITY.objects.filter(
                        TRC_SO_CODE=child_so,
                        TRC_CU_EXT_PROGR=child_cu,
                        TRC_FL_PHASE=other_phase
                    ).annotate(
                        MAT_CODE=Subquery(MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')).values('MAT_CODE')[:1]),
                        WM_NAME=Subquery(MD_WORKERS.objects.filter(WM_CODE=OuterRef('TRC_WM_CODE')).values('WM_NAME')[:1])
                    ).values(
                        'TRC_PP_CODE','TRC_MCH_CODE','TRC_SO_CODE',
                        'TRC_MAT_SAP_CODE','TRC_WM_CODE','TRC_START_TIME',
                        'TRC_END_TIME','TRC_CU_EXT_PROGR','TRC_FL_PHASE','MAT_CODE','WM_NAME'
                    ).first()

                if detail1:
                    node = {
                        'type': 'root',   # agar template bisa pakai format yang sama
                        'level': level,
                        'baris1': detail1,
                        'baris2': detail2
                    }
                    child_nodes.append(node)
                    child_nodes += get_child_cu_tree(child_so, child_cu, level+1)

            return child_nodes

        # --- Build traceability_tree ---
        for item in traceability_raw:
            if trc_fl_phase == 'C':
                baris1_phase, baris2_phase = 'C', 'P'
            elif trc_fl_phase == 'P':
                baris1_phase, baris2_phase = 'P', 'C'
            else:
                baris1_phase = item.get('TRC_FL_PHASE')
                baris2_phase = 'P' if baris1_phase == 'C' else 'C'

            # cari baris1
            if item['TRC_FL_PHASE'] == baris1_phase:
                baris1 = item
                baris2 = WMS_TRACEABILITY.objects.filter(
                    TRC_SO_CODE=item['TRC_SO_CODE'],
                    TRC_CU_EXT_PROGR=item['TRC_CU_EXT_PROGR'],
                    TRC_FL_PHASE=baris2_phase
                ).annotate(
                    MAT_CODE=Subquery(
                        MD_MATERIALS.objects.filter(
                            MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')
                        ).values('MAT_CODE')[:1]
                    ),
                    WM_NAME=Subquery(
                        MD_WORKERS.objects.filter(
                            WM_CODE=OuterRef('TRC_WM_CODE')
                        ).values('WM_NAME')[:1]
                    )
                ).values(
                    'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
                    'TRC_MAT_SAP_CODE', 'TRC_WM_CODE', 'TRC_START_TIME',
                    'TRC_END_TIME', 'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE',
                    'MAT_CODE', 'WM_NAME'
                ).first()

                node = {
                    'type': 'root',
                    'level': 0,
                    'baris1': baris1,
                    'baris2': baris2
                }
                traceability_tree.append(node)
                traceability_tree += get_child_cu_tree(item['TRC_SO_CODE'], item['TRC_CU_EXT_PROGR'], level=1)


    # === 7) Context ke template ===
    context = {
        'trc_list': trc_list,
        'machines': machines,
        'phase': phase,
        'date_shift_choices': date_shift_choices,
        'traceability_tree': traceability_tree,
        'selected_trc': trc_code,
        'selected_mch_info': mch_info,
        'selected_start_date': start_date_raw,
        'selected_end_date': end_date_raw,
        'selected_phase': trc_fl_phase,
    }

    return render(request, 'traceability_by_machine.html', context)












































# ======================= TRACEABILITY BY CONTAINMENT UNIT (CU) ==========================
def traceability_by_cu(request):
    # ------------ Parameter Pemanggilan ------------
    so_code = request.GET.get('source_code')
    mat_info = request.GET.get('mat_info')
    start_date_raw = request.GET.get('start_date')
    end_date_raw = request.GET.get('end_date')
    trc_fl_phase = request.GET.get('trc_fl_phase')

    # --- Helper: parsing tanggal|shift ---
    def parse_date_shift(raw_value):
        if not raw_value:
            return None, None
        try:
            date_part, shift_part = raw_value.split('|')
            date_obj = datetime.strptime(date_part, "%Y-%m-%d").date()
            return date_obj, int(shift_part)
        except Exception:
            return None, None

    # --- Helper: shift => datetime range ---
    def get_shift_datetime_range(date_obj, shift_num):
        if shift_num == 1:
            start_dt = datetime.combine(date_obj, time(0, 0, 0))
            end_dt = datetime.combine(date_obj, time(8, 0, 0))
        elif shift_num == 2:
            start_dt = datetime.combine(date_obj, time(8, 0, 0))
            end_dt = datetime.combine(date_obj, time(16, 0, 0))
        elif shift_num == 3:
            start_dt = datetime.combine(date_obj, time(16, 0, 0))
            end_dt = datetime.combine(date_obj, time(23, 59, 59))
        else:
            return None, None
        return start_dt, end_dt

    # --- Helper: jam => shift number ---
    def hour_to_shift(hour):
        if 0 <= hour < 8:
            return 1
        if 8 <= hour < 16:
            return 2
        return 3

    # --- Parse tanggal & shift dari parameter ---
    start_date, start_shift = parse_date_shift(start_date_raw)
    end_date, end_shift = parse_date_shift(end_date_raw)

    # --- Hitung rentang waktu shift global ---
    shift_start_dt, shift_end_dt = None, None
    if start_date and start_shift:
        shift_start_dt, _ = get_shift_datetime_range(start_date, start_shift)
    if end_date and end_shift:
        _, shift_end_dt = get_shift_datetime_range(end_date, end_shift)

    if shift_start_dt and not shift_end_dt:
        _, shift_end_dt = get_shift_datetime_range(start_date, start_shift)
    if shift_start_dt and shift_end_dt and shift_end_dt < shift_start_dt:
        shift_start_dt, shift_end_dt = shift_end_dt, shift_start_dt

    # ======================= DROPDOWN =======================
    # 1) Source
    sources = []
    if start_date and end_date and start_shift and end_shift:
        sources = (
            WMS_TRACEABILITY.objects
            .filter(TRC_START_TIME__range=(shift_start_dt, shift_end_dt))
            .values('TRC_SO_CODE')
            .distinct()
            .annotate(
                SO_DESC=Subquery(
                    MD_SOURCES.objects.filter(SO_CODE=OuterRef('TRC_SO_CODE')).values('SO_DESC')[:1]
                )
            )
            .order_by('TRC_SO_CODE')
        )

    # 2) CU List
    cu_list = []
    if so_code and shift_start_dt and shift_end_dt:
        cu_list = (
            WMS_TRACEABILITY.objects
            .filter(TRC_SO_CODE=so_code)
            .filter(TRC_START_TIME__range=(shift_start_dt, shift_end_dt))
            .values('TRC_SO_CODE', 'TRC_CU_EXT_PROGR')
            .distinct()
            .order_by('TRC_CU_EXT_PROGR')
        )

    # 3) Phase
    phase = (
        WMS_TRACEABILITY.objects
        .values('TRC_FL_PHASE')
        .distinct()
        .order_by('TRC_FL_PHASE')
    )

    # 4) Date+Shift Dropdown
    date_shift_choices = []
    date_shift_raw_qs = (
        WMS_TRACEABILITY.objects
        .annotate(date=TruncDate('TRC_START_TIME'))
        .annotate(hour=ExtractHour('TRC_START_TIME'))
        .values('date', 'hour')
        .distinct()
        .order_by('-date', 'hour')
    )
    seen = set()
    for rec in date_shift_raw_qs:
        date = rec.get('date')
        hour = rec.get('hour')
        if date is None or hour is None:
            continue
        shift = hour_to_shift(hour)
        key = (date, shift)
        if key in seen:
            continue
        seen.add(key)
        date_shift_choices.append({
            'value': f"{date.isoformat()}|{shift}",
            'label': f"{date.strftime('%d/%m/%Y')} - Shift {shift}"
        })

    # ======================= TRACEABILITY DATA =======================
        # ======================= TRACEABILITY DATA =======================
    traceability_cu = []
    data_cu = None
    materials = None

    traceability_qs = WMS_TRACEABILITY.objects.none()
    traceability_raw = []

    if so_code and mat_info and shift_start_dt and shift_end_dt and trc_fl_phase:
        try:
            trc_so_code, trc_cu_ext_progr = mat_info.split('|')
        except ValueError:
            trc_so_code, trc_cu_ext_progr = None, None

        # ------------------- AMBIL DATA CU & MATERIAL -------------------
        data_cu = {'TRC_SO_CODE': trc_so_code, 'TRC_CU_EXT_PROGR': trc_cu_ext_progr}
        materials = (
            WMS_TRACEABILITY.objects
            .filter(TRC_SO_CODE=trc_so_code, TRC_CU_EXT_PROGR=trc_cu_ext_progr)
            .annotate(
                MAT_CODE=Subquery(
                    MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')).values('MAT_CODE')[:1]
                ),
                MAT_DESC=Subquery(
                    MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')).values('MAT_DESC')[:1]
                )
            )
            .values('TRC_MAT_SAP_CODE', 'TRC_MAT_VARIANT', 'TRC_CNT_CODE', 'MAT_CODE', 'MAT_DESC')
            .first()
        )

        # ---- Query Utama Traceability ----
        traceability_qs = (
            WMS_TRACEABILITY.objects
            .filter(TRC_SO_CODE=trc_so_code, TRC_CU_EXT_PROGR=trc_cu_ext_progr)
            .filter(
                Q(TRC_START_TIME__range=(shift_start_dt, shift_end_dt)) |
                Q(TRC_END_TIME__range=(shift_start_dt, shift_end_dt)) |
                Q(TRC_END_TIME__gte=shift_start_dt, TRC_START_TIME__lte=shift_end_dt)
            )
            .order_by('TRC_START_TIME')
        )

        traceability_qs = traceability_qs.annotate(
            MAT_CODE=Subquery(
                MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')).values('MAT_CODE')[:1]
            ),
            WM_NAME=Subquery(
                MD_WORKERS.objects.filter(WM_CODE=OuterRef('TRC_WM_CODE')).values('WM_NAME')[:1]
            )
        )

        traceability_raw = list(traceability_qs.values(
            'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
            'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE',
            'TRC_MAT_SAP_CODE', 'TRC_WM_CODE',
            'TRC_START_TIME', 'TRC_END_TIME',
            'MAT_CODE', 'WM_NAME'
        ))


    # ===== Fungsi rekursif untuk child CU =====
    def get_child_cu_tree(parent_so, parent_cu, level=1):
        child_nodes = []
        parent_links = WMS_TRACEABILITY_CU.objects.filter(
            SO_CODE=parent_so,
            CU_EXT_PROGR=parent_cu
        )

        for link in parent_links:
            child_so = link.CHILD_SO_CODE
            child_cu = link.CHILD_CU_EXT_PROGR
            if not child_cu:
                continue

            # ambil baris1 fase utama (C atau P)
            detail1 = WMS_TRACEABILITY.objects.filter(
                TRC_SO_CODE=child_so,
                TRC_CU_EXT_PROGR=child_cu,
                TRC_FL_PHASE='C'  # default ambil C sebagai utama
            ).annotate(
                MAT_CODE=Subquery(MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')).values('MAT_CODE')[:1]),
                WM_NAME=Subquery(MD_WORKERS.objects.filter(WM_CODE=OuterRef('TRC_WM_CODE')).values('WM_NAME')[:1])
            ).values(
                'TRC_PP_CODE','TRC_MCH_CODE','TRC_SO_CODE',
                'TRC_MAT_SAP_CODE','TRC_WM_CODE','TRC_START_TIME',
                'TRC_END_TIME','TRC_CU_EXT_PROGR','TRC_FL_PHASE','MAT_CODE','WM_NAME'
            ).first()

            # ambil semua baris2 fase lawan
            baris2_list = []
            other_phase = 'P' if detail1 and detail1['TRC_FL_PHASE'] == 'C' else 'C'
            baris2_qs = WMS_TRACEABILITY.objects.filter(
                TRC_SO_CODE=child_so,
                TRC_CU_EXT_PROGR=child_cu,
                TRC_FL_PHASE=other_phase
            ).annotate(
                MAT_CODE=Subquery(MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')).values('MAT_CODE')[:1]),
                WM_NAME=Subquery(MD_WORKERS.objects.filter(WM_CODE=OuterRef('TRC_WM_CODE')).values('WM_NAME')[:1])
            ).values(
                'TRC_PP_CODE','TRC_MCH_CODE','TRC_SO_CODE',
                'TRC_MAT_SAP_CODE','TRC_WM_CODE','TRC_START_TIME',
                'TRC_END_TIME','TRC_CU_EXT_PROGR','TRC_FL_PHASE','MAT_CODE','WM_NAME'
            ).order_by('TRC_START_TIME')
            baris2_list = list(baris2_qs)

            # buat node walau baris1 None tapi baris2 ada
            if detail1 or baris2_list:
                node = {
                    'type': 'root',
                    'level': level,
                    'baris1': detail1,
                    'baris2': baris2_list
                }
                child_nodes.append(node)
                child_nodes += get_child_cu_tree(child_so, child_cu, level+1)

        return child_nodes


    # ===== Build traceability_tree =====
    traceability_cu = []

    # Tentukan fase utama dan fase lawan
    if trc_fl_phase == 'C':
        baris1_phase = 'C'
        baris2_phase = 'P'
    else:  # trc_fl_phase == 'P'
        baris1_phase = 'P'
        baris2_phase = 'C'

    # Ambil semua baris1 sesuai fase utama
    traceability_raw = traceability_qs.filter(TRC_FL_PHASE=baris1_phase).annotate(
        MAT_CODE=Subquery(MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')).values('MAT_CODE')[:1]),
        WM_NAME=Subquery(MD_WORKERS.objects.filter(WM_CODE=OuterRef('TRC_WM_CODE')).values('WM_NAME')[:1])
    ).values(
        'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
        'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE',
        'TRC_MAT_SAP_CODE', 'TRC_WM_CODE',
        'TRC_START_TIME', 'TRC_END_TIME', 'MAT_CODE', 'WM_NAME'
    )

    for baris1 in traceability_raw:
        # ambil semua baris2 fase lawan
        baris2_qs = WMS_TRACEABILITY.objects.filter(
            TRC_SO_CODE=baris1['TRC_SO_CODE'],
            TRC_CU_EXT_PROGR=baris1['TRC_CU_EXT_PROGR'],
            TRC_FL_PHASE=baris2_phase
        ).annotate(
            MAT_CODE=Subquery(MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')).values('MAT_CODE')[:1]),
            WM_NAME=Subquery(MD_WORKERS.objects.filter(WM_CODE=OuterRef('TRC_WM_CODE')).values('WM_NAME')[:1])
        ).values(
            'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
            'TRC_MAT_SAP_CODE','TRC_WM_CODE','TRC_START_TIME',
            'TRC_END_TIME','TRC_CU_EXT_PROGR','TRC_FL_PHASE','MAT_CODE','WM_NAME'
        ).order_by('TRC_START_TIME')
        baris2_list = list(baris2_qs)

        # buat node walau baris1 None tapi baris2 ada
        if baris1 or baris2_list:
            node = {
                'type': 'root',
                'level': 0,
                'baris1': baris1,
                'baris2': baris2_list
            }
            traceability_cu.append(node)

            # rekursif child CU
            traceability_cu += get_child_cu_tree(baris1['TRC_SO_CODE'], baris1['TRC_CU_EXT_PROGR'], level=1)



    # ======================= CONTEXT =======================
    context = {
        'sources': sources,
        'cu_list': cu_list,
        'phase': phase,
        'date_shift_choices': date_shift_choices,
        'selected_so_code': so_code,
        'selected_start_date': start_date_raw,
        'selected_end_date': end_date_raw,
        'selected_phase': trc_fl_phase,
        'mat_info': mat_info,
        'traceability_cu': traceability_cu,
        'data_cu': data_cu,
        'materials': materials,
    }

    return render(request, 'traceability_by_cu.html', context)

























































# ======================= TRACEABILITY MATERIALS ==========================
def traceability_by_materials(request):
    # ------------ Parameter Pemanggilan ------------
    sfc_code = request.GET.get('sfc_code')
    mat_info = request.GET.get('mat_info')
    start_date_raw = request.GET.get('start_date')
    end_date_raw = request.GET.get('end_date')
    trc_fl_phase = request.GET.get('trc_fl_phase')

    # --- Helper: parsing tanggal|shift ---
    def parse_date_shift(raw_value):
        if not raw_value:
            return None, None
        try:
            date_part, shift_part = raw_value.split('|')
            date_obj = datetime.strptime(date_part, "%Y-%m-%d").date()
            return date_obj, int(shift_part)
        except Exception:
            return None, None

    # --- Helper: shift => datetime range ---
    def get_shift_datetime_range(date_obj, shift_num):
        if shift_num == 1:
            start_dt = datetime.combine(date_obj, time(0, 0, 0))
            end_dt = datetime.combine(date_obj, time(8, 0, 0))
        elif shift_num == 2:
            start_dt = datetime.combine(date_obj, time(8, 0, 0))
            end_dt = datetime.combine(date_obj, time(16, 0, 0))
        elif shift_num == 3:
            start_dt = datetime.combine(date_obj, time(16, 0, 0))
            end_dt = datetime.combine(date_obj, time(23, 59, 59))
        else:
            return None, None
        return start_dt, end_dt

    # --- Helper: jam => shift number ---
    def hour_to_shift(hour):
        if 0 <= hour < 8:
            return 1
        if 8 <= hour < 16:
            return 2
        return 3

    # --- Parse tanggal & shift dari parameter ---
    start_date, start_shift = parse_date_shift(start_date_raw)
    end_date, end_shift = parse_date_shift(end_date_raw)

    # --- Hitung rentang waktu global berdasarkan shift ---
    shift_start_dt, shift_end_dt = None, None
    if start_date and start_shift:
        shift_start_dt, _ = get_shift_datetime_range(start_date, start_shift)
    if end_date and end_shift:
        _, shift_end_dt = get_shift_datetime_range(end_date, end_shift)

    # Kalau cuma 1 tanggal-shift → shift_end_dt = shift_end dari shift_start
    if shift_start_dt and not shift_end_dt:
        _, shift_end_dt = get_shift_datetime_range(start_date, start_shift)
    # Kalau end_date < start_date → dibalik biar aman
    if shift_start_dt and shift_end_dt and shift_end_dt < shift_start_dt:
        shift_start_dt, shift_end_dt = shift_end_dt, shift_start_dt

    # ======================= DROPDOWN =======================

    # --- 1) Dropdown SFC berdasarkan tanggal ---
    sfc_list = []
    if start_date and end_date:
        trace_materials = (
            WMS_TRACEABILITY.objects
            .filter(TRC_START_TIME__range=(shift_start_dt, shift_end_dt))
            .values('TRC_MAT_SAP_CODE')
            .distinct()
        )
        mat_codes = [row['TRC_MAT_SAP_CODE'] for row in trace_materials]

        sfc_list = (
            MD_SEMI_FINISHED_CLASSES.objects
            .filter(md_materials__MAT_SAP_CODE__in=mat_codes)
            .values('SFC_CODE', 'SFC_DESC')
            .distinct()
            .order_by('SFC_CODE')
        )

    # --- 2) Dropdown Material berdasarkan sfc_code & tanggal ---
    material_list = []
    if sfc_code and shift_start_dt and shift_end_dt:
        wms_mats = (
            WMS_TRACEABILITY.objects
            .filter(
                TRC_MAT_SAP_CODE__isnull=False,
                TRC_MAT_SAP_CODE__gt='',
                TRC_START_TIME__range=(shift_start_dt, shift_end_dt)
            )
            .values('TRC_MAT_SAP_CODE', 'TRC_CNT_CODE', 'TRC_MAT_VARIANT')
            .distinct()
            .order_by('TRC_MAT_SAP_CODE')
        )

        for mat in wms_mats:
            if MD_MATERIALS.objects.filter(
                MAT_SAP_CODE=mat['TRC_MAT_SAP_CODE'],
                SFC_CODE=sfc_code
            ).exists():
                mat_detail = MD_MATERIALS.objects.filter(
                    MAT_SAP_CODE=mat['TRC_MAT_SAP_CODE']
                ).values('MAT_CODE', 'MAT_DESC').first()

                material_list.append({
                    'TRC_MAT_SAP_CODE': mat['TRC_MAT_SAP_CODE'],
                    'TRC_CNT_CODE': mat['TRC_CNT_CODE'],
                    'TRC_MAT_VARIANT': mat['TRC_MAT_VARIANT'],
                    'MAT_CODE': mat_detail['MAT_CODE'] if mat_detail else '',
                    'MAT_DESC': mat_detail['MAT_DESC'] if mat_detail else '',
                })

    # --- 3) Dropdown Phase ---
    phase = (
        WMS_TRACEABILITY.objects
        .values('TRC_FL_PHASE')
        .distinct()
        .order_by('TRC_FL_PHASE')
    )

    # --- 4) Dropdown Date+Shift ---
    date_shift_choices = []
    date_shift_raw_qs = (
        WMS_TRACEABILITY.objects
        .annotate(date=TruncDate('TRC_START_TIME'))
        .annotate(hour=ExtractHour('TRC_START_TIME'))
        .values('date', 'hour')
        .distinct()
        .order_by('-date', 'hour')
    )

    seen = set()
    for rec in date_shift_raw_qs:
        date = rec.get('date')
        hour = rec.get('hour')
        if date is None or hour is None:
            continue
        shift = hour_to_shift(hour)
        key = (date, shift)
        if key in seen:
            continue
        seen.add(key)
        label = f"{date.strftime('%d/%m/%Y')} - Shift {shift}"
        value = f"{date.isoformat()}|{shift}"
        date_shift_choices.append({'value': value, 'label': label})

    # ======================= TRACEABILITY DATA =======================
    traceability_materials = []

    if sfc_code and mat_info and shift_start_dt and shift_end_dt and trc_fl_phase:
        traceability_qs = (
            WMS_TRACEABILITY.objects
            .filter(
                TRC_MAT_SAP_CODE=mat_info,
                TRC_FL_PHASE=trc_fl_phase
            )
            .filter(
                Q(TRC_START_TIME__range=(shift_start_dt, shift_end_dt)) |
                Q(TRC_END_TIME__range=(shift_start_dt, shift_end_dt)) |
                Q(TRC_END_TIME__gte=shift_start_dt, TRC_START_TIME__lte=shift_end_dt)
            )
            .order_by('TRC_START_TIME')
        )

        traceability_qs = traceability_qs.annotate(
            MAT_CODE=Subquery(
                MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')).values('MAT_CODE')[:1]
            ),
            WM_NAME=Subquery(
                MD_WORKERS.objects.filter(WM_CODE=OuterRef('TRC_WM_CODE')).values('WM_NAME')[:1]
            )
        )

        traceability_raw = list(traceability_qs.values(
            'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
            'TRC_MAT_SAP_CODE', 'TRC_CNT_CODE', 'TRC_MAT_VARIANT',
            'TRC_WM_CODE', 'TRC_START_TIME', 'TRC_END_TIME',
            'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE', 'MAT_CODE', 'WM_NAME'
        ))

        # === Rekursi Tree (tanpa perubahan besar) ===
        def get_child_materials_tree(parent_so, parent_cu, level=1):
            child_nodes = []

            # Ambil semua child dari parent di tabel CU
            child_links = WMS_TRACEABILITY_CU.objects.filter(
                SO_CODE=parent_so,
                CU_EXT_PROGR=parent_cu
            ).values('CHILD_SO_CODE', 'CHILD_CU_EXT_PROGR')

            for link in child_links:
                child_so = link['CHILD_SO_CODE']
                child_cu = link['CHILD_CU_EXT_PROGR']
                if not child_so or not child_cu:
                    continue

                # Cari data child di WMS_TRACEABILITY berdasarkan child_so & child_cu
                child_qs = WMS_TRACEABILITY.objects.filter(
                    TRC_SO_CODE=child_so,
                    TRC_CU_EXT_PROGR=child_cu
                ).annotate(
                    MAT_CODE=Subquery(
                        MD_MATERIALS.objects.filter(
                            MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')
                        ).values('MAT_CODE')[:1]
                    ),
                    WM_NAME=Subquery(
                        MD_WORKERS.objects.filter(
                            WM_CODE=OuterRef('TRC_WM_CODE')
                        ).values('WM_NAME')[:1]
                    )
                ).values(
                    'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
                    'TRC_MAT_SAP_CODE', 'TRC_WM_CODE', 'TRC_START_TIME',
                    'TRC_END_TIME', 'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE',
                    'MAT_CODE', 'WM_NAME'
                ).order_by('TRC_START_TIME')

                # Bagi data berdasarkan phase
                baris1 = child_qs.filter(TRC_FL_PHASE='P').first()
                baris2_list = list(child_qs.filter(TRC_FL_PHASE='C'))

                if baris1 or baris2_list:
                    node = {
                        'type': 'child',
                        'level': level,
                        'baris1': baris1,
                        'baris2': baris2_list,
                    }
                    child_nodes.append(node)

                    # Rekursif ke level berikutnya
                    child_nodes += get_child_materials_tree(child_so, child_cu, level + 1)

            return child_nodes



        for item in traceability_raw:
            # Tentukan pasangan fase utama dan lawan
            baris1_phase, baris2_phase = ('C', 'P') if trc_fl_phase == 'C' else ('P', 'C')

            if item['TRC_FL_PHASE'] == baris1_phase:
                baris1 = item

                # ========== Ambil baris2 ==========
                if trc_fl_phase == 'P':
                    # Jika form-phase = 'P', ambil baris2 (fase 'C') TANPA filter waktu
                    baris2_qs = WMS_TRACEABILITY.objects.filter(
                        TRC_SO_CODE=item['TRC_SO_CODE'],
                        TRC_CU_EXT_PROGR=item['TRC_CU_EXT_PROGR'],
                        TRC_FL_PHASE='C'
                    )

                elif trc_fl_phase == 'C':
                    # Jika form-phase = 'C', ambil baris2 (fase 'P') TANPA filter tanggal & shift juga
                    baris2_qs = WMS_TRACEABILITY.objects.filter(
                        TRC_SO_CODE=item['TRC_SO_CODE'],
                        TRC_CU_EXT_PROGR=item['TRC_CU_EXT_PROGR'],
                        TRC_FL_PHASE='P'
                    )

                else:
                    # Kondisi fallback (jarang kepakai, tapi aman)
                    baris2_qs = WMS_TRACEABILITY.objects.filter(
                        TRC_SO_CODE=item['TRC_SO_CODE'],
                        TRC_CU_EXT_PROGR=item['TRC_CU_EXT_PROGR'],
                        TRC_FL_PHASE=baris2_phase
                    )

                # ========== Annotate hasil baris2 ==========
                baris2_list = baris2_qs.annotate(
                    MAT_CODE=Subquery(
                        MD_MATERIALS.objects.filter(
                            MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')
                        ).values('MAT_CODE')[:1]
                    ),
                    WM_NAME=Subquery(
                        MD_WORKERS.objects.filter(
                            WM_CODE=OuterRef('TRC_WM_CODE')
                        ).values('WM_NAME')[:1]
                    )
                ).values(
                    'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
                    'TRC_MAT_SAP_CODE', 'TRC_WM_CODE', 'TRC_START_TIME',
                    'TRC_END_TIME', 'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE',
                    'MAT_CODE', 'WM_NAME'
                ).order_by('TRC_START_TIME')

                # ========== Bentuk node ==========
                node = {
                    'type': 'root',
                    'level': 0,
                    'baris1': baris1,
                    'baris2': list(baris2_list)
                }
                traceability_materials.append(node)

                # Tetap lanjut ke rekursif (child)
                traceability_materials += get_child_materials_tree(
                    item['TRC_SO_CODE'],
                    item['TRC_CU_EXT_PROGR'],
                    1
                )

    # ======================= CONTEXT =======================
    context = {
        'sfc_list': sfc_list,
        'material_list': material_list,
        'phase': phase,
        'date_shift_choices': date_shift_choices,
        'traceability_materials': traceability_materials,
        'selected_sfc': sfc_code,
        'selected_mat_info': mat_info,
        'selected_start_date': start_date_raw,
        'selected_end_date': end_date_raw,
        'selected_phase': trc_fl_phase,
    }

    return render(request, 'traceability_by_materials.html', context)








































































# ================= TRACING BARCODE ===================
def tracing_barcode(request):
    barcode_list = TRC_BASIC_TABLE.objects.values_list('TRC_BARCODE', flat=True).distinct()
    selected_barcode = request.GET.get('barcode')
    material_detail = None
    traceability = []

    # ================= FUNCTION RECURSIVE ===================
    def get_child_trace(so_code, cu_ext, level=1):
        tree_rows = []

        children = WMS_TRACEABILITY_CU.objects.filter(
            SO_CODE=so_code,
            CU_EXT_PROGR=cu_ext
        ).values('CHILD_SO_CODE', 'CHILD_CU_EXT_PROGR')

        for c in children:
            child_so = c['CHILD_SO_CODE']
            child_cu = c['CHILD_CU_EXT_PROGR']

            wms = WMS_TRACEABILITY.objects.filter(
                TRC_SO_CODE=child_so,
                TRC_CU_EXT_PROGR=child_cu,
                TRC_FL_PHASE='P'
            ).first()

            if wms:
                mat = MD_MATERIALS.objects.filter(
                    MAT_SAP_CODE=wms.TRC_MAT_SAP_CODE
                ).first()
                sfc_code = mat.SFC_CODE if mat else ""

                baris1 = {
                    'TRC_SO_CODE': wms.TRC_SO_CODE,
                    'TRC_CU_EXT_PROGR': wms.TRC_CU_EXT_PROGR,
                    'TRC_FL_PHASE' : wms.TRC_FL_PHASE,
                    'TRC_PP_CODE' : wms.TRC_PP_CODE,
                    'MAT_CODE' : mat.MAT_CODE if mat else '',
                    'TRC_START_TIME' : wms.TRC_START_TIME,
                    'TRC_END_TIME' : wms.TRC_END_TIME,
                    'TRC_MAT_SAP_CODE': wms.TRC_MAT_SAP_CODE,
                    'MAT_DESC': mat.MAT_DESC if mat else '',
                    'SFC_DESC': sfc_code,
                    'TRC_MCH_CODE' : wms.TRC_MCH_CODE,
                    'PP_DESC' : production.PP_DESC if production else '',
                    'WM_NAME' : worker.WM_NAME if worker else '',
                }

                mt_desc = ''
                bom = MD_BOM.objects.filter(MAT_SAP_CODE=wms.TRC_MAT_SAP_CODE).first()
                if bom:
                    mt = MD_MACHINE_TYPES.objects.filter(MT_CODE=bom.MT_CODE).first()
                    mt_desc = mt.MT_DESC if mt else ''

                baris2 = [{
                    'TRC_SO_CODE': wms_root.TRC_SO_CODE,
                    'TRC_CU_EXT_PROGR': wms_root.TRC_CU_EXT_PROGR,
                    'TRC_FL_PHASE' : wms_root.TRC_FL_PHASE,
                    'TRC_PP_CODE' : wms_root.TRC_PP_CODE,
                    'TRC_START_TIME' : wms_root.TRC_START_TIME,
                    'TRC_END_TIME' : wms_root.TRC_END_TIME,
                    'TRC_MCH_CODE': wms_root.TRC_MCH_CODE,
                    'MT_DESC': mt_desc,
                    'TRC_MAT_SAP_CODE': wms_root.TRC_MAT_SAP_CODE,
                    'SFC_DESC': sfc_code,
                    'WM_NAME' : worker.WM_NAME if worker else '',
                    'MAT_CODE' : mat.MAT_CODE if mat else '',
                }]

                tree_rows.append({
                    'baris1': baris1,
                    'baris2': baris2,
                    'level': level
                })

                tree_rows.extend(get_child_trace(child_so, child_cu, level + 1))

        return tree_rows
    # ================= END RECURSIVE ===================

    if selected_barcode:
        trc_entry = TRC_BASIC_TABLE.objects.filter(TRC_BARCODE=selected_barcode).first()

        if trc_entry:
            material = MD_MATERIALS.objects.filter(MAT_SAP_CODE=trc_entry.MAT_SAP_CODE).first()
            material_detail = {
                'MAT_CODE': material.MAT_CODE if material else '',
                'MAT_SAP_CODE': trc_entry.MAT_SAP_CODE,
                'MAT_DESC': material.MAT_DESC if material else '',
                'pp_code': trc_entry.PP_CODE,
                'mch_code': trc_entry.MCH_CODE,
            }

            child_mats = MD_BOM.objects.filter(
                MAT_SAP_CODE=trc_entry.MAT_SAP_CODE
            ).values_list('CHILD_MAT_SAP_CODE', flat=True)

            wms_all = WMS_TRACEABILITY.objects.filter(
                TRC_MAT_SAP_CODE__in=child_mats,
                TRC_MCH_CODE=trc_entry.MCH_CODE,
                TRC_PP_CODE=trc_entry.PP_CODE,
                TRC_FL_EMPTY='T'
            ).values(
                'TRC_SO_CODE',
                'TRC_CU_EXT_PROGR'
            ).distinct()

            for root in wms_all:
                so = root['TRC_SO_CODE']
                cu = root['TRC_CU_EXT_PROGR']

                wms_root = WMS_TRACEABILITY.objects.filter(
                    TRC_SO_CODE=so,
                    TRC_CU_EXT_PROGR=cu,
                    TRC_FL_PHASE='P'
                ).first()
                if not wms_root:
                    continue

                mat = MD_MATERIALS.objects.filter(
                    MAT_SAP_CODE=wms_root.TRC_MAT_SAP_CODE
                ).first()
                sfc_code = mat.SFC_CODE if mat else ''

                # Ambil PP_DESC dari MD_PRODUCTION_PHASES berdasarkan PP_CODE
                production = None
                if wms_root.TRC_PP_CODE:
                    production = MD_PRODUCTION_PHASES.objects.filter(PP_CODE=wms_root.TRC_PP_CODE).first()

                worker = None

                worker_code = getattr(wms_root, 'TRC_WM_CODE', None)
                if worker_code:
                    worker = MD_WORKERS.objects.filter(WM_CODE=worker_code).first()

                baris1 = {
                    'TRC_SO_CODE': wms_root.TRC_SO_CODE,
                    'TRC_CU_EXT_PROGR': wms_root.TRC_CU_EXT_PROGR,
                    'TRC_FL_PHASE' : wms_root.TRC_FL_PHASE,
                    'TRC_PP_CODE' : wms_root.TRC_PP_CODE,
                    'MAT_CODE' : mat.MAT_CODE if mat else '',
                    'TRC_START_TIME' : wms_root.TRC_START_TIME,
                    'TRC_END_TIME' : wms_root.TRC_END_TIME,
                    'TRC_MAT_SAP_CODE': wms_root.TRC_MAT_SAP_CODE,
                    'MAT_DESC': mat.MAT_DESC if mat else '',
                    'SFC_DESC': sfc_code,
                    'TRC_MCH_CODE' : wms_root.TRC_MCH_CODE,
                    'PP_DESC' : production.PP_DESC if production else '',
                    'WM_NAME' : worker.WM_NAME if worker else '',
                }

                mt_desc = ''
                bom = MD_BOM.objects.filter(MAT_SAP_CODE=wms_root.TRC_MAT_SAP_CODE).first()
                if bom:
                    mt = MD_MACHINE_TYPES.objects.filter(MT_CODE=bom.MT_CODE).first()
                    mt_desc = mt.MT_DESC if mt else ''

                baris2 = [{
                    'TRC_SO_CODE': wms_root.TRC_SO_CODE,
                    'TRC_CU_EXT_PROGR': wms_root.TRC_CU_EXT_PROGR,
                    'TRC_FL_PHASE' : wms_root.TRC_FL_PHASE,
                    'TRC_PP_CODE' : wms_root.TRC_PP_CODE,
                    'TRC_START_TIME' : wms_root.TRC_START_TIME,
                    'TRC_END_TIME' : wms_root.TRC_END_TIME,
                    'TRC_MCH_CODE': wms_root.TRC_MCH_CODE,
                    'MT_DESC': mt_desc,
                    'TRC_MAT_SAP_CODE': wms_root.TRC_MAT_SAP_CODE,
                    'SFC_DESC': sfc_code,
                    'WM_NAME' : worker.WM_NAME if worker else '',
                    'MAT_CODE' : mat.MAT_CODE if mat else '',
                }]

                traceability.append({
                    'baris1': baris1,
                    'baris2': baris2,
                    'level': 0
                })

                traceability.extend(get_child_trace(so, cu, 1))

    return render(request, "tracing_barcode.html", {
        'barcode_list': barcode_list,
        'selected_barcode': selected_barcode,
        'material_detail': material_detail,
        'traceability': traceability,
    })