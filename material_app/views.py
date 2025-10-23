from django.shortcuts import render
from material_app.models import MD_MATERIALS, MD_SEMI_FINISHED_CLASSES, MD_BOM, DC_PRODUCTION_DATA, MD_WORKERS, WMS_TRACEABILITY, MD_PRODUCTION_PHASES, WMS_TRACEABILITY_CU, MD_SOURCES
from datetime import datetime, timedelta, time
from django.db.models import OuterRef, Subquery
from django.db.models.functions import TruncDate, ExtractHour
from django.db.models import OuterRef, Subquery, Q
from django.db.models import Sum, Count
from django.core.serializers.json import DjangoJSONEncoder
import json

# =================== MENU DASHBOARD ========================
from datetime import date

# =================== MENU DASHBOARD ========================
def dashboard(request):
    # ===================== TOTAL DATA SECTION =====================
    selected_date = request.GET.get('date')
    if not selected_date:
        selected_date = date.today().strftime("%Y-%m-%d")  # default hari ini

    total_consumed = total_produced = total_produksi = 0

    try:
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
        total_consumed = WMS_TRACEABILITY.objects.filter(
            TRC_FL_PHASE='C',
            TRC_START_TIME__date=date_obj
        ).count()
        total_produced = WMS_TRACEABILITY.objects.filter(
            TRC_FL_PHASE='P',
            TRC_START_TIME__date=date_obj
        ).count()
        total_produksi = (
            DC_PRODUCTION_DATA.objects
            .filter(PS_DATE__date=date_obj)
            .aggregate(total=Sum('PS_QUANTITY'))['total'] or 0
        )
        total_produksi = round(total_produksi, 2)
    except ValueError:
        selected_date = None


    # ===================== FILTER FORM SECTION =====================
    sfc_code = request.GET.get('sfc_code')
    mat_sap_code = request.GET.get('mat_sap_code')
    ps_date = request.GET.get('ps_date')  # urutan pertama (tanggal)

    #  Dropdown Tanggal (PS_DATE)
    daftar_tanggal = (
        DC_PRODUCTION_DATA.objects
        .values_list('PS_DATE', flat=True)
        .distinct()
        .order_by('PS_DATE')
    )

    #  Dropdown SFC_CODE
    daftar_sfc = (
        MD_SEMI_FINISHED_CLASSES.objects
        .filter(SFC_CODE__in=['AL', 'AX'])
        .values_list('SFC_CODE', flat=True)
        .distinct()
        .order_by('SFC_CODE')
    )

    # Dropdown MAT_SAP_CODE berdasarkan PS_DATE + SFC_CODE
    daftar_mat_sap = []
    if ps_date and sfc_code:
        try:
            date_obj = datetime.strptime(ps_date, "%Y-%m-%d").date()

            # ambil semua material berdasarkan SFC_CODE
            mat_codes = list(
                MD_MATERIALS.objects
                .filter(SFC_CODE=sfc_code)
                .values_list('MAT_SAP_CODE', flat=True)
            )

            # filter data produksi berdasarkan tanggal dan material yang sesuai
            daftar_mat_sap = (
                DC_PRODUCTION_DATA.objects
                .filter(
                    PS_DATE__date=date_obj,
                    MAT_SAP_CODE__in=mat_codes
                )
                .values_list('MAT_SAP_CODE', flat=True)
                .distinct()
                .order_by('MAT_SAP_CODE')
            )
        except ValueError:
            pass

    # ===================== TABEL PRODUKSI SECTION =====================
    tabel_data = []
    if sfc_code and mat_sap_code and ps_date:
        try:
            selected_dt = datetime.strptime(ps_date, "%Y-%m-%d").date()

            produksi_qs = (
                DC_PRODUCTION_DATA.objects
                .filter(
                    MAT_SAP_CODE=mat_sap_code,
                    PS_DATE__date=selected_dt
                )
                .values('MAT_SAP_CODE', 'MCH_CODE', 'PS_START_PROD', 'PS_END_PROD', 'PS_DATE', 'SHF_CODE')
                .order_by('PS_START_PROD')
            )

            # Ambil mapping MAT_SAP_CODE → SFC_CODE → SFC_DESC
            mat_sap_codes = [row['MAT_SAP_CODE'] for row in produksi_qs]
            mat_sfc_map = dict(
                MD_MATERIALS.objects
                .filter(MAT_SAP_CODE__in=mat_sap_codes)
                .values_list('MAT_SAP_CODE', 'SFC_CODE')
            )
            sfc_codes = list(set(mat_sfc_map.values()))
            sfc_desc_map = dict(
                MD_SEMI_FINISHED_CLASSES.objects
                .filter(SFC_CODE__in=sfc_codes)
                .values_list('SFC_CODE', 'SFC_DESC')
            )

            for row in produksi_qs:
                start = row['PS_START_PROD']
                end = row['PS_END_PROD']
                durasi_jam = ((end - start).total_seconds() / 3600 if start and end else 0)
                sfc_code_row = mat_sfc_map.get(row['MAT_SAP_CODE'])
                sfc_desc_row = sfc_desc_map.get(sfc_code_row, '')

                tabel_data.append({
                    'ps_date': row['PS_DATE'],
                    'mat_sap_code': row['MAT_SAP_CODE'],
                    'mch_code': row['MCH_CODE'],
                    'shf_code': row['SHF_CODE'],
                    'sfc_code': sfc_code_row,
                    'sfc_desc': sfc_desc_row,
                    'ps_start_prod': start,
                    'ps_end_prod': end,
                    'durasi_jam': round(durasi_jam, 2),
                })
        except ValueError:
            pass

    # ===================== CONTEXT UNTUK TEMPLATE =====================
    context = {
        'title': 'Dashboard Produksi',
        'selected_date': selected_date,
        'total_consumed': total_consumed,
        'total_produced': total_produced,
        'total_produksi': total_produksi,

        # Data dropdown
        'daftar_tanggal': daftar_tanggal,
        'daftar_sfc': daftar_sfc,
        'daftar_mat_sap': daftar_mat_sap,

        # Selected option
        'selected_ps_date': ps_date,
        'selected_sfc': sfc_code,
        'selected_mat_sap': mat_sap_code,

        # Data tabel
        'tabel_data': tabel_data,
    }

    return render(request, 'templates2/dashboard.html', context)









































# ============ INFORMASI IP MATERIALS  =============
def get_material_detail(mat_code):
    try:
        mat = MD_MATERIALS.objects.filter(MAT_CODE=mat_code).first()

        if not mat:
            return {}
        
        bom = MD_BOM.objects.filter(MAT_SAP_CODE=mat.MAT_SAP_CODE).first()

        return {
            'ip_code': mat.MAT_CODE,
            'spec': mat.MAT_SPEC_CODE,
            'mat_desc': mat.MAT_DESC,
            'bom_status': bom.BV_STATUS if bom else '-',
        }
    except Exception as e:
        
        print("Error in get_material_detail:", e)
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




# ================= MENU PRODUCTIONS ==================
def daftar_produksi(request):
    sfc_list = MD_SEMI_FINISHED_CLASSES.objects.filter(SFC_CODE__in=['AL', 'AX'])

    sfc_code = request.GET.get('sfc_code')
    mat_info = request.GET.get('mat_info')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    error_message = None

    # Cek selisih tanggal
    if start_date and end_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            delta_days = (end_dt - start_dt).days
            if delta_days > 30:
                error_message = "Data tidak boleh lebih dari 30 hari!"
                start_date = end_date = None
        except ValueError:
            error_message = "Format tanggal salah!"

    production_list = []
    materials = []

    # jika ada filter maka pake all tanpa limit 
    if sfc_code or mat_info or start_date or end_date:
        production_list_query = DC_PRODUCTION_DATA.objects.all()
    else:
        production_list_query = DC_PRODUCTION_DATA.objects.all().order_by('-PS_DATE')[:10]



    # Ambil mapping MAT_SAP_CODE -> MAT_CODE
    mat_map = {}
    if sfc_code:
        mat_map = dict(MD_MATERIALS.objects.filter(SFC_CODE=sfc_code).values_list('MAT_SAP_CODE', 'MAT_CODE'))

        # Untuk dropdown IP Materials
        unique_mat_sap_codes = DC_PRODUCTION_DATA.objects.filter(MAT_SAP_CODE__in=mat_map.keys()).values_list('MAT_SAP_CODE', flat=True).distinct()
        materials = [{'MAT_SAP_CODE': code, 'MAT_CODE': mat_map.get(code, '')} for code in unique_mat_sap_codes]

    # Filter SFC 
    if sfc_code and mat_map:
        production_list_query = production_list_query.filter(MAT_SAP_CODE__in=mat_map.keys())

    # Filter IP Materials
    if mat_info:
        production_list_query = production_list_query.filter(MAT_SAP_CODE=mat_info)

    # Jika user tidak isi tanggal, otomatis set 3 hari terakhir
    if (sfc_code or mat_info) and not start_date and not end_date:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=2)  
        start_date = start_dt.strftime("%Y-%m-%d")
        end_date = end_dt.strftime("%Y-%m-%d")

    # Filter tanggal
    if start_date:
        production_list_query = production_list_query.filter(PS_DATE__date__gte=start_date)
    if end_date:
        production_list_query = production_list_query.filter(PS_DATE__date__lte=end_date)

    # Ambil data untuk tabel
    production_list_query = production_list_query.values(
        'MAT_SAP_CODE',
        'PP_CODE',
        'MCH_CODE',
        'SHF_CODE',
        'PS_QUANTITY',
        'PS_START_PROD',
        'PS_END_PROD',
        'PS_DATE'
    )
    production_list = list(production_list_query)
    for p in production_list:
        p['MAT_CODE'] = MD_MATERIALS.objects.filter(MAT_SAP_CODE=p['MAT_SAP_CODE']).first()
        p['MAT_CODE'] = p['MAT_CODE'].MAT_CODE if p['MAT_CODE'] else ""

    context = {
        'sfc_list': sfc_list,
        'materials': materials,
        'production_list': production_list,
        'selected_sfc': sfc_code,
        'selected_mat_info': mat_info,
        'selected_start_date': start_date,
        'selected_end_date': end_date,
        'error_message': error_message,
    }
    return render(request, 'daftar_produksi.html', context)







# ========================= TRACEABILITY BY MACHINE ==========================
def traceability_by_machine(request):
    # --- Ambil parameter dari form (GET) ---
    trc_code = request.GET.get('trc_code')               # production phases(TRC_PP_CODE)
    mch_info = request.GET.get('mch_info')               # "TRC_PP_CODE|TRC_MCH_CODE"
    start_date_raw = request.GET.get('start_date')       # "YYYY-mm-dd|shift"
    end_date_raw = request.GET.get('end_date')           # "YYYY-mm-dd|shift"
    trc_fl_phase = request.GET.get('trc_fl_phase')       # C atau P

    # --- parse tanggal|shift ---
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

    # Menentukan waktu mulai dan selesai berdasarkan shift
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

    # konversi jam ke shift
    def hour_to_shift(hour):
        if 0 <= hour < 8:
            return 1
        if 8 <= hour < 16:
            return 2
        return 3

    start_date, start_shift = parse_date_shift(start_date_raw)
    end_date, end_shift = parse_date_shift(end_date_raw)

    # 1) Daftar form production phase (TRC_PP_CODE)
    pp_desc_subquery = MD_PRODUCTION_PHASES.objects.filter(
        PP_CODE=OuterRef('TRC_PP_CODE')
    ).values('PP_DESC')[:1]

    trc_list = (
        WMS_TRACEABILITY.objects
        .annotate(PP_DESC=Subquery(pp_desc_subquery))
        .values('TRC_PP_CODE', 'PP_DESC')
        .distinct()
        .order_by('TRC_PP_CODE')
    )

    # 2) Daftar mesin (hanya muncul ketika trc_code dipilih)
    machines = []
    if trc_code:
        machines = (
            WMS_TRACEABILITY.objects
            .filter(TRC_PP_CODE=trc_code)
            .values('TRC_PP_CODE', 'TRC_MCH_CODE')
            .distinct()
            .order_by('TRC_MCH_CODE')
        )

    # 3) Daftar phase 
    phase_qs = WMS_TRACEABILITY.objects.all()

    if trc_code:
        # Filter berdasarkan production phase
        phase_qs = phase_qs.filter(TRC_PP_CODE=trc_code)

        # Pengecualian FL_PHASE
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

    # 4) Daftar pilihan tanggal|shift
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

    # --- default kosong ---
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

    # --- Context untuk render ke template ---
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
















# ============== TRACEABILITY BY CONTAINMENT UNIT (CU) ===================
def traceability_by_cu(request):
    # ============= Ambil Parameter dari Form ============
    so_code = request.GET.get('source_code')
    mat_info = request.GET.get('mat_info')
    start_date_raw = request.GET.get('start_date')
    end_date_raw = request.GET.get('end_date')
    trc_fl_phase = request.GET.get('trc_fl_phase')

    # Helper parse date|shift
    def parse_date_shift(raw_value):
        if not raw_value:
            return None, None
        try:
            date_part, shift_part = raw_value.split('|')
            date_obj = datetime.strptime(date_part, "%Y-%m-%d").date()
            return date_obj, int(shift_part)
        except:
            return None, None

    # Helper shift => datetime range
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

    def hour_to_shift(hour):
        if 0 <= hour < 8: return 1
        if 8 <= hour < 16: return 2
        return 3

    start_date, start_shift = parse_date_shift(start_date_raw)
    end_date, end_shift = parse_date_shift(end_date_raw)

    # Dropdown source
    sources = (
        WMS_TRACEABILITY.objects
        .values('TRC_SO_CODE')
        .distinct()
        .annotate(
            SO_DESC=Subquery(
                MD_SOURCES.objects.filter(SO_CODE=OuterRef('TRC_SO_CODE')).values('SO_DESC')[:1]
            )
        )
        .order_by('TRC_SO_CODE')
    )

    # Dropdown CU
    cu_list = []
    if so_code:
        cu_list = (
            WMS_TRACEABILITY.objects
            .filter(TRC_SO_CODE=so_code)
            .values('TRC_SO_CODE', 'TRC_CU_EXT_PROGR')
            .distinct()
            .order_by('TRC_CU_EXT_PROGR')
        )

    # Dropdown phase
    phase = (
        WMS_TRACEABILITY.objects
        .values('TRC_FL_PHASE')
        .distinct()
        .order_by('TRC_FL_PHASE')
    )

    # Dropdown tanggal + shift
    date_shift_choices = []
    raw_dates = (
        WMS_TRACEABILITY.objects
        .annotate(date=TruncDate('TRC_START_TIME'))
        .annotate(hour=ExtractHour('TRC_START_TIME'))
        .values('date', 'hour')
        .distinct()
        .order_by('-date', 'hour')
    )

    seen = set()
    for rec in raw_dates:
        date = rec['date']
        hour = rec['hour']
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

    # ============== Tampil data =================
    traceability_cu = []
    data_cu = None
    materials = None

    if so_code and mat_info and start_date and end_date and trc_fl_phase:
        try:
            trc_so_code, trc_cu_ext_progr = mat_info.split('|')
        except ValueError:
            trc_so_code, trc_cu_ext_progr = None, None
        data_cu = {
            'TRC_SO_CODE': trc_so_code,
            'TRC_CU_EXT_PROGR': trc_cu_ext_progr
        }
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
            .values(
                'TRC_MAT_SAP_CODE',
                'TRC_MAT_VARIANT',
                'TRC_CNT_CODE',
                'MAT_CODE',
                'MAT_DESC'
            )
            .first()
        )

        traceability_qs = WMS_TRACEABILITY.objects.filter(
            TRC_SO_CODE=trc_so_code,
            TRC_CU_EXT_PROGR=trc_cu_ext_progr,
        )


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
            'TRC_START_TIME', 'TRC_END_TIME', 'MAT_CODE', 'WM_NAME'
        ))

# ============ Pengaturan Child Parent ====================
        def get_child_cu_tree(parent_so, parent_cu, level=1):
            child_nodes = []

            if trc_fl_phase == 'P':
                parent_links = WMS_TRACEABILITY_CU.objects.filter(
                    CHILD_SO_CODE=parent_so,
                    CHILD_CU_EXT_PROGR=parent_cu
                ).values('SO_CODE', 'CU_EXT_PROGR')

                for link in parent_links:
                    child_so = link['SO_CODE']
                    child_cu = link['CU_EXT_PROGR']

                    if not child_so or not child_cu:
                        continue

                    # Ambil detail baris1 (FL_PHASE = 'P')
                    detail1 = WMS_TRACEABILITY.objects.filter(
                        TRC_SO_CODE=child_so,
                        TRC_CU_EXT_PROGR=child_cu,
                        TRC_FL_PHASE='P'
                    ).annotate(
                        MAT_CODE=Subquery(MD_MATERIALS.objects.filter(
                            MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')
                        ).values('MAT_CODE')[:1]),
                        WM_NAME=Subquery(MD_WORKERS.objects.filter(
                            WM_CODE=OuterRef('TRC_WM_CODE')
                        ).values('WM_NAME')[:1])
                    ).values(
                        'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
                        'TRC_MAT_SAP_CODE', 'TRC_WM_CODE', 'TRC_START_TIME',
                        'TRC_END_TIME', 'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE', 'MAT_CODE', 'WM_NAME'
                    ).first()

                    # Ambil detail baris2 (FL_PHASE = 'C')
                    detail2 = WMS_TRACEABILITY.objects.filter(
                        TRC_SO_CODE=child_so,
                        TRC_CU_EXT_PROGR=child_cu,
                        TRC_FL_PHASE='C'
                    ).annotate(
                        MAT_CODE=Subquery(MD_MATERIALS.objects.filter(
                            MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')
                        ).values('MAT_CODE')[:1]),
                        WM_NAME=Subquery(MD_WORKERS.objects.filter(
                            WM_CODE=OuterRef('TRC_WM_CODE')
                        ).values('WM_NAME')[:1])
                    ).values(
                        'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
                        'TRC_MAT_SAP_CODE', 'TRC_WM_CODE', 'TRC_START_TIME',
                        'TRC_END_TIME', 'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE', 'MAT_CODE', 'WM_NAME'
                    ).first()

                    if detail1:
                        node = {
                            'type': 'root',
                            'level': level,
                            'baris1': detail1,
                            'baris2': detail2
                        }
                        child_nodes.append(node)
                        # Rekursif ke child dari data baru
                        child_nodes += get_child_cu_tree(child_so, child_cu, level + 1)

            else:
                # Phase C - logika lama tetap
                parent_links = WMS_TRACEABILITY_CU.objects.filter(
                    SO_CODE=parent_so,
                    CU_EXT_PROGR=parent_cu
                ).values('CHILD_SO_CODE', 'CHILD_CU_EXT_PROGR')

                for link in parent_links:
                    child_so = link['CHILD_SO_CODE']
                    child_cu = link['CHILD_CU_EXT_PROGR']

                    if not child_so or not child_cu:
                        continue

                    detail1 = WMS_TRACEABILITY.objects.filter(
                        TRC_SO_CODE=child_so,
                        TRC_CU_EXT_PROGR=child_cu,
                        TRC_FL_PHASE='C'
                    ).annotate(
                        MAT_CODE=Subquery(MD_MATERIALS.objects.filter(
                            MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')
                        ).values('MAT_CODE')[:1]),
                        WM_NAME=Subquery(MD_WORKERS.objects.filter(
                            WM_CODE=OuterRef('TRC_WM_CODE')
                        ).values('WM_NAME')[:1])
                    ).values(
                        'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
                        'TRC_MAT_SAP_CODE', 'TRC_WM_CODE', 'TRC_START_TIME',
                        'TRC_END_TIME', 'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE', 'MAT_CODE', 'WM_NAME'
                    ).order_by('TRC_START_TIME').first()

                    detail2 = None
                    if detail1:
                        other_phase = 'P' if detail1['TRC_FL_PHASE'] == 'C' else 'C'
                        detail2 = WMS_TRACEABILITY.objects.filter(
                            TRC_SO_CODE=child_so,
                            TRC_CU_EXT_PROGR=child_cu,
                            TRC_FL_PHASE=other_phase
                        ).annotate(
                            MAT_CODE=Subquery(MD_MATERIALS.objects.filter(
                                MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')
                            ).values('MAT_CODE')[:1]),
                            WM_NAME=Subquery(MD_WORKERS.objects.filter(
                                WM_CODE=OuterRef('TRC_WM_CODE')
                            ).values('WM_NAME')[:1])
                        ).values(
                            'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
                            'TRC_MAT_SAP_CODE', 'TRC_WM_CODE', 'TRC_START_TIME',
                            'TRC_END_TIME', 'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE', 'MAT_CODE', 'WM_NAME'
                        ).first()

                    if detail1:
                        node = {
                            'type': 'root',
                            'level': level,
                            'baris1': detail1,
                            'baris2': detail2
                        }
                        child_nodes.append(node)
                        child_nodes += get_child_cu_tree(child_so, child_cu, level + 1)
            return child_nodes

        # --- Build traceability_tree ---
        if trc_fl_phase == 'C':
            baris2_phase = 'P'
            baris1_phase = 'P'

            baris2_qs = traceability_qs.filter(TRC_FL_PHASE=baris2_phase)
            traceability_raw = list(baris2_qs.values(
                'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
                'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE',
                'TRC_MAT_SAP_CODE', 'TRC_WM_CODE',
                'TRC_START_TIME', 'TRC_END_TIME', 'MAT_CODE', 'WM_NAME'
            ))

            for baris2 in traceability_raw:
                baris1 = WMS_TRACEABILITY.objects.filter(
                    TRC_SO_CODE=baris2['TRC_SO_CODE'],
                    TRC_CU_EXT_PROGR=baris2['TRC_CU_EXT_PROGR'],
                    TRC_FL_PHASE=baris1_phase
                ).annotate(
                    MAT_CODE=Subquery(
                        MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')).values('MAT_CODE')[:1]
                    ),
                    WM_NAME=Subquery(
                        MD_WORKERS.objects.filter(WM_CODE=OuterRef('TRC_WM_CODE')).values('WM_NAME')[:1]
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
                traceability_cu.append(node)
                traceability_cu += get_child_cu_tree(baris2['TRC_SO_CODE'], baris2['TRC_CU_EXT_PROGR'], level=1)

        elif trc_fl_phase == 'P':
            baris1_phase = 'P'
            baris2_phase = 'C'

            # Ambil data baris1 dari WMS_TRACEABILITY yang phase = 'P'
            baris1_qs = WMS_TRACEABILITY.objects.filter(
                TRC_SO_CODE=trc_so_code,
                TRC_CU_EXT_PROGR=trc_cu_ext_progr,
                TRC_FL_PHASE=baris1_phase
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

            for baris1 in baris1_qs:
                # Ambil pelengkap baris2 dari WMS_TRACEABILITY phase = 'C'
                baris2 = WMS_TRACEABILITY.objects.filter(
                    TRC_SO_CODE=baris1['TRC_SO_CODE'],
                    TRC_CU_EXT_PROGR=baris1['TRC_CU_EXT_PROGR'],
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
                traceability_cu.append(node)
                traceability_cu += get_child_cu_tree(baris1['TRC_SO_CODE'], baris1['TRC_CU_EXT_PROGR'], level=1)


    # === Context For Template ===
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























#  ======================= TRACEABILITY MATERIALS ==========================
def traceability_by_materials(request):
    allowed_sfc_code = ['BR','C0', 'CC', 'CE', 'CP', 'CX', 'FB', 'RC', 'TB', 'TT']

    # ------------ Parameter Pemanggilan ------------
    sfc_code = request.GET.get('sfc_code')
    mat_info = request.GET.get('mat_info')
    start_date_raw = request.GET.get('start_date')
    end_date_raw = request.GET.get('end_date')
    trc_fl_phase = request.GET.get('trc_fl_phase')

    # --- helper parse tanggal|shift ---
    def parse_date_shift(raw_value):
        if not raw_value:
            return None, None
        try:
            date_part, shift_part = raw_value.split('|')
            date_obj = datetime.strptime(date_part, "%Y-%m-%d").date()
            return date_obj, int(shift_part)
        except Exception:
            return None, None

    start_date, start_shift = parse_date_shift(start_date_raw)
    end_date, end_shift = parse_date_shift(end_date_raw)

    def hour_to_shift(hour):
        if 0 <= hour < 8: return 1
        if 8 <= hour < 16: return 2
        return 3

    # --- 1) Dropdown SFC ---
    sfc_list = (
        MD_SEMI_FINISHED_CLASSES.objects
        .filter(SFC_CODE__in=allowed_sfc_code)
        .values('SFC_CODE', 'SFC_DESC')
        .distinct()
        .order_by('SFC_CODE')
    )

    # --- 2) Dropdown Materials ---
    material_list = []
    if sfc_code:
        wms_mats = (
            WMS_TRACEABILITY.objects
            .filter(TRC_MAT_SAP_CODE__isnull=False, TRC_MAT_SAP_CODE__gt='')
            .values('TRC_MAT_SAP_CODE', 'TRC_CNT_CODE', 'TRC_MAT_VARIANT')
            .distinct()
            .order_by('TRC_MAT_SAP_CODE')
        )

        for mat in wms_mats:
            if MD_MATERIALS.objects.filter(
                MAT_SAP_CODE=mat['TRC_MAT_SAP_CODE'], SFC_CODE=sfc_code
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

    # ----- Default kosong -----
    traceability_materials = []

    # --- 5) Build Traceability Tree ---
    if sfc_code and mat_info and start_date and end_date and trc_fl_phase:

        # Query utama
        traceability_qs = (
            WMS_TRACEABILITY.objects
            .filter(TRC_MAT_SAP_CODE=mat_info)
            .filter(TRC_START_TIME__date__range=(start_date, end_date))
            .filter(TRC_FL_PHASE=trc_fl_phase)
            .order_by('TRC_START_TIME')
        )

        # Filter shift (time and date)
        if start_shift:
            shift_start = None
            shift_end = None
            if start_shift == 1:
                shift_start = datetime.combine(start_date, time(0, 0, 0))
                shift_end = datetime.combine(start_date, time(8, 0, 0))
            elif start_shift == 2:
                shift_start = datetime.combine(start_date, time(8, 0, 0))
                shift_end = datetime.combine(start_date, time(16, 0, 0))
            elif start_shift == 3:
                shift_start = datetime.combine(start_date, time(16, 0, 0))
                # shift_end di hari berikutnya jam 00:00, berarti sampai 23:59:59
                shift_end = datetime.combine(start_date + timedelta(days=1), time(0, 0, 0))

            if shift_start and shift_end:
                traceability_qs = traceability_qs.filter(
                    Q(TRC_END_TIME__gte=shift_start, TRC_START_TIME__lte=shift_end) |
                    Q(TRC_START_TIME__range=(shift_start, shift_end)) |
                    Q(TRC_END_TIME__range=(shift_start, shift_end))
                )

        # Annotasi MAT_CODE dan WM_NAME
        traceability_qs = traceability_qs.annotate(
            MAT_CODE=Subquery(
                MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')).values('MAT_CODE')[:1]
            ),
            WM_NAME=Subquery(
                MD_WORKERS.objects.filter(WM_CODE=OuterRef('TRC_WM_CODE')).values('WM_NAME')[:1]
            )
        )

        traceability_raw = list(traceability_qs.values(
            'TRC_PP_CODE','TRC_MCH_CODE','TRC_SO_CODE',
            'TRC_MAT_SAP_CODE','TRC_CNT_CODE','TRC_MAT_VARIANT',
            'TRC_WM_CODE','TRC_START_TIME','TRC_END_TIME',
            'TRC_CU_EXT_PROGR','TRC_FL_PHASE','MAT_CODE','WM_NAME'
        ))




        # === Rekursi Traceability Tree ===
        def get_child_materials_tree(parent_so, parent_cu, level=1):
            child_nodes = []

            if trc_fl_phase == 'P':
                parent_links = WMS_TRACEABILITY_CU.objects.filter(
                    CHILD_SO_CODE=parent_so,
                    CHILD_CU_EXT_PROGR=parent_cu
                ).values('SO_CODE', 'CU_EXT_PROGR')

                for link in parent_links:
                    child_so = link['SO_CODE']
                    child_cu = link['CU_EXT_PROGR']

                    if not child_so or not child_cu:
                        continue

                    # ========= Ambil detail baris1 (FL_PHASE = 'P') ==========
                    detail1 = WMS_TRACEABILITY.objects.filter(
                        TRC_SO_CODE=child_so,
                        TRC_CU_EXT_PROGR=child_cu,
                        TRC_FL_PHASE='P'
                    ).annotate(
                        MAT_CODE=Subquery(MD_MATERIALS.objects.filter(
                            MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')
                        ).values('MAT_CODE')[:1]),
                        WM_NAME=Subquery(MD_WORKERS.objects.filter(
                            WM_CODE=OuterRef('TRC_WM_CODE')
                        ).values('WM_NAME')[:1])
                    ).values(
                        'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
                        'TRC_MAT_SAP_CODE', 'TRC_WM_CODE', 'TRC_START_TIME',
                        'TRC_END_TIME', 'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE', 'MAT_CODE', 'WM_NAME'
                    ).order_by('TRC_START_TIME').first()

                    # ======== Ambil detail baris2 (FL_PHASE = 'C') ===========
                    detail2 = WMS_TRACEABILITY.objects.filter(
                        TRC_SO_CODE=child_so,
                        TRC_CU_EXT_PROGR=child_cu,
                        TRC_FL_PHASE='C'
                    ).annotate(
                        MAT_CODE=Subquery(MD_MATERIALS.objects.filter(
                            MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')
                        ).values('MAT_CODE')[:1]),
                        WM_NAME=Subquery(MD_WORKERS.objects.filter(
                            WM_CODE=OuterRef('TRC_WM_CODE')
                        ).values('WM_NAME')[:1])
                    ).values(
                        'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
                        'TRC_MAT_SAP_CODE', 'TRC_WM_CODE', 'TRC_START_TIME',
                        'TRC_END_TIME', 'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE', 'MAT_CODE', 'WM_NAME'
                    ).first()

                    if detail1:
                        node = {
                            'type': 'root',
                            'level': level,
                            'baris1': detail1,
                            'baris2': detail2
                        }
                        child_nodes.append(node)
                        # Rekursif ke child dari data baru
                        child_nodes += get_child_materials_tree(child_so, child_cu, level + 1)
            else:
                # Phase C - logika lama tetap
                parent_links = WMS_TRACEABILITY_CU.objects.filter(
                    SO_CODE=parent_so,
                    CU_EXT_PROGR=parent_cu
                ).values('CHILD_SO_CODE', 'CHILD_CU_EXT_PROGR')

                for link in parent_links:
                    child_so = link['CHILD_SO_CODE']
                    child_cu = link['CHILD_CU_EXT_PROGR']

                    if not child_so or not child_cu:
                        continue

                    detail1 = WMS_TRACEABILITY.objects.filter(
                        TRC_SO_CODE=child_so,
                        TRC_CU_EXT_PROGR=child_cu,
                        TRC_FL_PHASE='C'
                    ).annotate(
                        MAT_CODE=Subquery(MD_MATERIALS.objects.filter(
                            MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')
                        ).values('MAT_CODE')[:1]),
                        WM_NAME=Subquery(MD_WORKERS.objects.filter(
                            WM_CODE=OuterRef('TRC_WM_CODE')
                        ).values('WM_NAME')[:1])
                    ).values(
                        'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
                        'TRC_MAT_SAP_CODE', 'TRC_WM_CODE', 'TRC_START_TIME',
                        'TRC_END_TIME', 'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE', 'MAT_CODE', 'WM_NAME'
                    ).order_by('TRC_START_TIME').first()

                    detail2 = None
                    if detail1:
                        other_phase = 'P' if detail1['TRC_FL_PHASE'] == 'C' else 'C'
                        detail2 = WMS_TRACEABILITY.objects.filter(
                            TRC_SO_CODE=child_so,
                            TRC_CU_EXT_PROGR=child_cu,
                            TRC_FL_PHASE=other_phase
                        ).annotate(
                            MAT_CODE=Subquery(MD_MATERIALS.objects.filter(
                                MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')
                            ).values('MAT_CODE')[:1]),
                            WM_NAME=Subquery(MD_WORKERS.objects.filter(
                                WM_CODE=OuterRef('TRC_WM_CODE')
                            ).values('WM_NAME')[:1])
                        ).values(
                            'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE',
                            'TRC_MAT_SAP_CODE', 'TRC_WM_CODE', 'TRC_START_TIME',
                            'TRC_END_TIME', 'TRC_CU_EXT_PROGR', 'TRC_FL_PHASE', 'MAT_CODE', 'WM_NAME'
                        ).first()

                    if detail1:
                        node = {
                            'type': 'root',
                            'level': level,
                            'baris1': detail1,
                            'baris2': detail2
                        }
                        child_nodes.append(node)
                        child_nodes += get_child_materials_tree(child_so, child_cu, level + 1)
            return child_nodes

        # === BUILD ROOT & CHILD KALO FL PHASE ( VIEW DATA BUILD P == C OR C == P) ===
        for item in traceability_raw:
            baris1_phase, baris2_phase = ('C','P') if trc_fl_phase=='C' else ('P','C')
            if item['TRC_FL_PHASE'] == baris1_phase:
                baris1 = item
                baris2 = WMS_TRACEABILITY.objects.filter(
                    TRC_SO_CODE=item['TRC_SO_CODE'],
                    TRC_CU_EXT_PROGR=item['TRC_CU_EXT_PROGR'],
                    TRC_FL_PHASE=baris2_phase
                ).annotate(
                    MAT_CODE=Subquery(MD_MATERIALS.objects.filter(MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')).values('MAT_CODE')[:1]),
                    WM_NAME=Subquery(MD_WORKERS.objects.filter(WM_CODE=OuterRef('TRC_WM_CODE')).values('WM_NAME')[:1])
                ).values(
                    'TRC_PP_CODE','TRC_MCH_CODE','TRC_SO_CODE',
                    'TRC_MAT_SAP_CODE','TRC_WM_CODE','TRC_START_TIME',
                    'TRC_END_TIME','TRC_CU_EXT_PROGR','TRC_FL_PHASE','MAT_CODE','WM_NAME'
                ).order_by('TRC_START_TIME').first()

                node = {
                    'type': 'root',
                    'level': 0,
                    'baris1': baris1,
                    'baris2': baris2
                }
                traceability_materials.append(node)
                traceability_materials += get_child_materials_tree(item['TRC_SO_CODE'], item['TRC_CU_EXT_PROGR'], level=1)

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
