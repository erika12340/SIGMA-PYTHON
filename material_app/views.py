from django.shortcuts import render
from material_app.models import MD_MATERIALS, MD_SEMI_FINISHED_CLASSES, MD_BOM, DC_PRODUCTION_DATA, MD_WORKERS, WMS_TRACEABILITY, MD_PRODUCTION_PHASES, WMS_TRACEABILITY_CU, MD_SOURCES
from datetime import datetime, timedelta
from django.db.models import OuterRef, Subquery
from django.db.models.functions import TruncDate
from django.db.models import Q
from django.db.models import Min




# =================== MENU DASHBOARD ========================
def index(request):
    return render(request, 'templates2/dashboard.html', {'title': 'Dashboard'})

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
def data_produksi(request):
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

    # Filter SFC jika dipilih
    if sfc_code and mat_map:
        production_list_query = production_list_query.filter(MAT_SAP_CODE__in=mat_map.keys())

    # Filter IP Materials
    if mat_info:
        production_list_query = production_list_query.filter(MAT_SAP_CODE=mat_info)

    # Jika user tidak isi tanggal, otomatis set 3 hari terakhir (berlaku baik pilih SFC atau IP Materials)
    if (sfc_code or mat_info) and not start_date and not end_date:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=2)  # 3 hari (hari ini + 2 sebelumnya)
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
    return render(request, 'data_produksi.html', context)

















from django.shortcuts import render
from django.db.models import Q
from datetime import datetime, timedelta, time
from collections import defaultdict

# Models (asumsikan sudah ada)
from .models import WMS_TRACEABILITY, MD_PRODUCTION_PHASES, MD_WORKERS, WMS_TRACEABILITY_CU

def traceability_by_machine(request):
    # 1. Ambil pilihan filter (production phase, machine, fl_phase, tanggal shift)
    trc_list = (
        WMS_TRACEABILITY.objects.values('TRC_PP_CODE')
        .distinct()
        .order_by('TRC_PP_CODE')
    )
    # Dapatkan deskripsi phase dari MD_PRODUCTION_PHASES (assume PP_CODE sebagai pk)
    # Buat dict supaya gampang akses PP_DESC
    phase_desc_map = {
        p.PP_CODE: p.PP_DESC for p in MD_PRODUCTION_PHASES.objects.all()
    }

    # Buat list trc_list dengan PP_DESC
    trc_list = [
        {
            'TRC_PP_CODE': trc['TRC_PP_CODE'],
            'PP_DESC': phase_desc_map.get(trc['TRC_PP_CODE'], '')
        } for trc in trc_list
    ]

    # Ambil pilihan production phase
    selected_trc = request.GET.get('trc_code')

    # 2. Ambil machine yang ada di phase terpilih
    machines_qs = WMS_TRACEABILITY.objects.all()
    if selected_trc:
        machines_qs = machines_qs.filter(TRC_PP_CODE=selected_trc)
    machines_qs = machines_qs.values('TRC_PP_CODE', 'TRC_MCH_CODE').distinct().order_by('TRC_MCH_CODE')
    machines = list(machines_qs)

    selected_mch_info = request.GET.get('mch_info')  # format "TRC_PP_CODE|TRC_MCH_CODE"

    # 3. FL Phase
    phase = WMS_TRACEABILITY.objects.values('TRC_FL_PHASE').distinct().order_by('TRC_FL_PHASE')

    selected_phase = request.GET.get('trc_fl_phase')

    # 4. Tanggal & Shift
    # Buat pilihan tanggal + shift dari data WMS_TRACEABILITY, misal dari TRC_START_TIME
    dates_qs = WMS_TRACEABILITY.objects.values_list('TRC_START_TIME', flat=True).distinct().order_by('TRC_START_TIME')
    date_shift_choices = []

    def get_shift_label(dt, shift_num):
        return f"{dt.date()} Shift {shift_num} ({'00.00-08.00' if shift_num == 1 else '08.00-16.00' if shift_num == 2 else '16.00-00.00'})"

    # Ambil distinct tanggal dengan shift
    date_shift_set = set()
    for dt in dates_qs:
        if not dt:
            continue
        # Tentukan shift
        hour = dt.hour
        shift = 3 if hour >= 16 else 2 if hour >= 8 else 1
        # Simpan sebagai string unik: "YYYY-MM-DD|shift"
        key = f"{dt.date()}|{shift}"
        if key not in date_shift_set:
            date_shift_set.add(key)
            label = get_shift_label(dt, shift)
            date_shift_choices.append({'value': key, 'label': label})

    selected_start_date = request.GET.get('start_date')  # format "YYYY-MM-DD|shift"
    selected_end_date = request.GET.get('end_date')

    # Helper untuk parse shift ke waktu mulai dan berakhir
    def shift_to_time(date_str, shift_num):
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
        if shift_num == 1:
            start = datetime.combine(d, time(0, 0))
            end = datetime.combine(d, time(8, 0))
        elif shift_num == 2:
            start = datetime.combine(d, time(8, 0))
            end = datetime.combine(d, time(16, 0))
        else:
            # Shift 3: 16:00 to next day 00:00
            start = datetime.combine(d, time(16, 0))
            end = datetime.combine(d + timedelta(days=1), time(0, 0))
        return start, end

    # 5. Filter data WMS_TRACEABILITY berdasarkan filter yang dipilih
    trace_qs = WMS_TRACEABILITY.objects.all()

    if selected_trc:
        trace_qs = trace_qs.filter(TRC_PP_CODE=selected_trc)

    if selected_mch_info:
        try:
            pp_code, mch_code = selected_mch_info.split('|')
            trace_qs = trace_qs.filter(TRC_PP_CODE=pp_code, TRC_MCH_CODE=mch_code)
        except:
            pass

    if selected_phase:
        trace_qs = trace_qs.filter(TRC_FL_PHASE=selected_phase)

    # Filter tanggal berdasarkan start_date dan end_date
    if selected_start_date:
        start_date_str, start_shift_str = selected_start_date.split('|')
        start_shift_num = int(start_shift_str)
        start_dt, _ = shift_to_time(start_date_str, start_shift_num)
        trace_qs = trace_qs.filter(TRC_START_TIME__gte=start_dt)

    if selected_end_date:
        end_date_str, end_shift_str = selected_end_date.split('|')
        end_shift_num = int(end_shift_str)
        _, end_dt = shift_to_time(end_date_str, end_shift_num)
        trace_qs = trace_qs.filter(TRC_END_TIME__lte=end_dt)

    # Ambil semua data filtered ke list
    trace_data = list(trace_qs.order_by('TRC_START_TIME'))

    # Ambil semua data WMS_TRACEABILITY_CU
    cu_data = list(WMS_TRACEABILITY_CU.objects.all())

    # Buat dict mapping CU_EXT_PROGR ke list anaknya
    children_map = defaultdict(list)
    for cu in cu_data:
        if cu.CHILD_CU_EXT_PROGR:
            children_map[cu.CU_EXT_PROGR].append(cu.CHILD_CU_EXT_PROGR)

    # Buat dict mapping TRC_CU_EXT_PROGR ke data dari WMS_TRACEABILITY_CU
    cu_map = {cu.CU_EXT_PROGR: cu for cu in cu_data}

    # Buat dict mapping TRC_CU_EXT_PROGR ke WMS_TRACEABILITY
    trace_map = defaultdict(list)
    for row in trace_data:
        trace_map[row.TRC_CU_EXT_PROGR].append(row)

    # 6. Build tree dengan rekursif fungsi
    traceability_tree = []

    # Helper: ambil WM_NAME dari MD_WORKERS via TRC_WM_CODE
    wm_codes = {w.WM_CODE: w.WM_NAME for w in MD_WORKERS.objects.all()}

    def build_tree(cu_ext_progr, level=0):
        rows = trace_map.get(cu_ext_progr, [])
        for row in rows:
            # Baris 1 data
            wm_name = wm_codes.get(row.TRC_WM_CODE, '')

            # Baris 2: ambil dari WMS_TRACEABILITY_CU berdasarkan TRC_CU_EXT_PROGR
            cu_row = cu_map.get(row.TRC_CU_EXT_PROGR)

            # ambil info operator dari MD_WORKERS jika ada
            operator_wm_code = getattr(cu_row, 'OPERATOR_WM_CODE', None)
            operator_wm_name = wm_codes.get(operator_wm_code, '') if operator_wm_code else ''

            traceability_tree.append({
                'level': level,
                'TRC_SO_CODE': row.TRC_SO_CODE,
                'TRC_CU_EXT_PROGR': row.TRC_CU_EXT_PROGR,
                'MAT_CODE': row.MAT_CODE,
                'TRC_MAT_SAP_CODE': row.TRC_MAT_SAP_CODE,
                'TRC_START_TIME': row.TRC_START_TIME.strftime('%Y-%m-%d %H:%M'),
                'TRC_END_TIME': row.TRC_END_TIME.strftime('%Y-%m-%d %H:%M'),
                'TRC_WM_CODE': row.TRC_WM_CODE,
                'WM_NAME': wm_name,

                # baris 2
                'PP_CODE': row.TRC_PP_CODE,
                'MCH_CODE': row.TRC_MCH_CODE,
                'PRODUCTION_DATE': row.TRC_START_TIME.strftime('%Y-%m-%d'),
                'OPERATOR_PROD': {
                    'WM_CODE': operator_wm_code or '',
                    'WM_NAME': operator_wm_name
                },
            })

            # 7. Build children recursively
            children = children_map.get(row.TRC_CU_EXT_PROGR, [])
            for child_cu in children:
                build_tree(child_cu, level + 1)

    # Tentukan roots untuk tree, yaitu TRC_CU_EXT_PROGR yang tidak ada sebagai CHILD_CU_EXT_PROGR di data lain
    all_cu_ext_progr = set(cu_map.keys())
    all_child_cu_ext_progr = {cu.CHILD_CU_EXT_PROGR for cu in cu_data if cu.CHILD_CU_EXT_PROGR}
    root_cu_ext_progrs = all_cu_ext_progr - all_child_cu_ext_progr

    # Jika ingin tampilkan tree dari root yang ada di trace_data (filter sesuai), bisa pakai:
    root_cu_candidates = set(row.TRC_CU_EXT_PROGR for row in trace_data)
    roots = root_cu_ext_progrs.intersection(root_cu_candidates)

    # Build tree mulai dari roots
    for root in roots:
        build_tree(root)

    context = {
        'trc_list': trc_list,
        'machines': machines,
        'phase': phase,
        'date_shift_choices': date_shift_choices,
        'selected_trc': selected_trc,
        'selected_mch_info': selected_mch_info,
        'selected_phase': selected_phase,
        'selected_start_date': selected_start_date,
        'selected_end_date': selected_end_date,
        'traceability_tree': traceability_tree,
    }
    return render(request, 'traceability_by_machine.html', context)





















































# ====================================traceability by containment unit =================================================
def traceability_by_cu(request):
    # FILTER SOURCE YANG DIIJINKAN
    allowed_so_codes = ['00CE', '00CP', '00CX', '00FB', '00RC', '00TB', '00TT', 'SM11', 'SM21', 'TLV1']

    # GET PARAMETER DARI FORM
    so_code = request.GET.get('source_code')
    mat_info = request.GET.get('mat_info')
    start_date_raw = request.GET.get('start_date')
    end_date_raw = request.GET.get('end_date')
    trc_fl_phase = request.GET.get('trc_fl_phase')

    # PARSE CU EXT
    cu_ext = None
    if mat_info:
        try:
            _, cu_ext = mat_info.split('|')
        except ValueError:
            pass

    # PARSE TANGGAL DAN SHIFT
    def parse_date_shift(raw_value):
        try:
            date_part, shift_part = raw_value.split('|')
            return date_part, shift_part
        except Exception:
            return None, None

    start_date_str, _ = parse_date_shift(start_date_raw) if start_date_raw else (None, None)
    end_date_str, _ = parse_date_shift(end_date_raw) if end_date_raw else (None, None)

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None
    except ValueError:
        start_date = None
        end_date = None

    # DROPDOWN SOURCES
    sources = (
        WMS_TRACEABILITY.objects
        .filter(TRC_SO_CODE__in=allowed_so_codes)
        .values('TRC_SO_CODE')
        .distinct()
        .annotate(
            SO_DESC=Subquery(
                MD_SOURCES.objects.filter(SO_CODE=OuterRef('TRC_SO_CODE')).values('SO_DESC')[:1]
            )
        )
        .order_by('TRC_SO_CODE')
    )

    # DROPDOWN CU
    cu_list = []
    if so_code and so_code in allowed_so_codes:
        cu_list = (
            WMS_TRACEABILITY.objects
            .filter(TRC_SO_CODE=so_code)
            .values('TRC_SO_CODE', 'TRC_CU_EXT_PROGR')
            .distinct()
            .order_by('TRC_CU_EXT_PROGR')
        )

    # DROPDOWN PHASE
    phase = (
        WMS_TRACEABILITY.objects
        .values('TRC_FL_PHASE')
        .distinct()
        .order_by('TRC_FL_PHASE')
    )

    # DROPDOWN TANGGAL & SHIFT
    date_shift_raw = (
        WMS_TRACEABILITY.objects
        .annotate(date=TruncDate('TRC_START_TIME'))
        .values('TRC_START_TIME', 'date')
        .annotate(shift=Subquery(
            DC_PRODUCTION_DATA.objects.filter(
                PS_START_PROD=OuterRef('TRC_START_TIME')
            ).values('SHF_CODE')[:1]
        ))
        .values('date', 'shift')
        .distinct()
        .order_by('-date')
    )

    date_shift_choices = [
        {
            'value': f"{item['date']}|{item['shift']}",
            'label': f"{item['date'].strftime('%d/%m/%Y')} - {item['shift']}"
        }
        for item in date_shift_raw if item['shift']
    ]

    # INISIALISASI
    traceability_tree = []
    traceability_raw_cu = []

    # HANYA JALANKAN JIKA SEMUA FILTER DIISI
    if all([so_code, cu_ext, trc_fl_phase, start_date, end_date]):
        # SUBQUERY
        so_code_query = WMS_TRACEABILITY_CU.objects.filter(
            SO_CODE=OuterRef('TRC_SO_CODE')
        ).values('SO_CODE')[:1]

        wm_name_subquery = MD_WORKERS.objects.filter(
            WM_CODE=OuterRef('TRC_WM_CODE')
        ).values('WM_NAME')[:1]

        # QUERY DATA TRACEABILITY
        traceability_qs = WMS_TRACEABILITY.objects.filter(
            TRC_START_TIME__date__range=(start_date, end_date),
            TRC_SO_CODE__in=allowed_so_codes
        ).annotate(
            MAT_CODE=Subquery(so_code_query),
            WM_NAME=Subquery(wm_name_subquery),
        ).filter(
            TRC_SO_CODE=so_code,
            TRC_CU_EXT_PROGR=cu_ext,
            TRC_FL_PHASE=trc_fl_phase
        )

        traceability_raw_cu = list(
            traceability_qs.values(
                'TRC_PP_CODE',
                'TRC_MCH_CODE',
                'TRC_SO_CODE',
                'TRC_MAT_SAP_CODE',
                'TRC_WM_CODE',
                'TRC_START_TIME',
                'TRC_END_TIME',
                'TRC_CU_EXT_PROGR',
                'MAT_CODE',
                'WM_NAME',
            )
        )

        # PROSES TREE
        roots = set((item['TRC_SO_CODE'], item['TRC_CU_EXT_PROGR']) for item in traceability_raw_cu)

        cu_data = WMS_TRACEABILITY_CU.objects.filter(
            SO_CODE__in=[so for so, cu in roots]
        ).values('SO_CODE', 'CU_EXT_PROGR', 'CHILD_CU_CODE')

        cu_map = {}
        for cu in cu_data:
            key = (cu['SO_CODE'], cu['CU_EXT_PROGR'])
            cu_map.setdefault(key, []).append(cu['CHILD_CU_CODE'])

        for root in roots:
            so_code, cu_ext_progr = root
            key_display = f"{so_code} - {cu_ext_progr}"
            root_data = next((item for item in traceability_raw_cu if item['TRC_SO_CODE'] == so_code and item['TRC_CU_EXT_PROGR'] == cu_ext_progr), None)
            traceability_tree.append({
                'type': 'root',
                'key': key_display,
                'level': 0,
                **(root_data if root_data else {})
            })
            children_cu_codes = cu_map.get(root, [])
            for item in traceability_raw_cu:
                if item['TRC_SO_CODE'] == so_code and item['TRC_CU_EXT_PROGR'] in children_cu_codes:
                    traceability_tree.append({
                        'type': 'child',
                        'parent_key': key_display,
                        'level': 1,
                        **item
                    })

    # DATA CU & MATERIALS
    data_cu = None
    materials = None

    if cu_ext and so_code:
        data_cu = WMS_TRACEABILITY.objects.filter(
            TRC_SO_CODE=so_code,
            TRC_CU_EXT_PROGR=cu_ext
        ).order_by('-TRC_START_TIME').first()

    if data_cu:
        materials = MD_MATERIALS.objects.filter(
            MAT_SAP_CODE=data_cu.TRC_MAT_SAP_CODE
        ).first()

    get_materials = None
    if cu_ext:
        get_materials = MD_MATERIALS.objects.filter(MAT_CODE=cu_ext).first()

    # CONTEXT KE TEMPLATE
    context = {
        'sources': sources,
        'cu_list': cu_list,
        'phase': phase,
        'date_shift_choices': date_shift_choices,
        'selected_so_code': so_code,
        'selected_cu_ext': cu_ext,
        'selected_start_date': start_date_raw,
        'selected_end_date': end_date_raw,
        'selected_phase': trc_fl_phase,
        'mat_info': mat_info,
        'get_materials': get_materials,
        'data_cu': data_cu,
        'materials': materials,
        'traceability_tree': traceability_tree,
    }

    return render(request, 'traceability_by_cu.html', context)

















# =========================== TRACEABILITY BY MATERIALS =======================
def traceability_by_materials(request):
    # ----------------- FILTER SFC_CODE YANG TAMPIL ----------------------
    allowed_sfc_code = ['C0', 'CC', 'CE', 'CP', 'CX', 'FB', 'RC', 'TB', 'TT']


    # --------------- MENGAMBIL PARAMETER QUERY --------------------
    sfc_code = request.GET.get('sfc_code')
    mat_code = request.GET.get('mat_code')
    start_date_raw = request.GET.get('start_date')
    end_date_raw = request.GET.get('end_date')
    trc_fl_phase = request.GET.get('trc_fl_phase')


    # --------------- DATE|SHIFT -----------------
    def parse_date_shift(raw_value):
        try:
            date_part, shift_part = raw_value.split('|')
            return date_part, shift_part
        except Exception:
            return None, None

    start_date_str, _ = parse_date_shift(start_date_raw) if start_date_raw else (None, None)
    end_date_str, _ = parse_date_shift(end_date_raw) if end_date_raw else (None, None)

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None
    except ValueError:
        start_date = end_date = None


    # ---------------------- DROPDOWN SFC CODE -----------------------
    sfc_list = (
        MD_SEMI_FINISHED_CLASSES.objects
        .filter(SFC_CODE__in=allowed_sfc_code)
        .values('SFC_CODE', 'SFC_DESC')
        .distinct()
        .order_by('SFC_CODE')
    )


    # ------------- DROPDOWN MATERIALS --------------
    material_list = (
        MD_MATERIALS.objects
        .values('MAT_CODE', 'MAT_SAP_CODE', 'MAT_VARIANT', 'CNT_CODE', 'MAT_DESC')
        .distinct()
        .order_by('MAT_CODE')
    )


    # ------------- DROPDOWN TRACEABILITY PHASE ----------
    phase = (
        WMS_TRACEABILITY.objects
        .values('TRC_FL_PHASE')
        .distinct()
        .order_by('TRC_FL_PHASE')
    )


    # ---------------DROPDOWN DATE AND SHIFT --------------
    date_shift_raw = (
        WMS_TRACEABILITY.objects
        .annotate(date=TruncDate('TRC_START_TIME'))
        .values('TRC_START_TIME', 'date')
        .annotate(shift=Subquery(
            DC_PRODUCTION_DATA.objects.filter(
                PS_START_PROD=OuterRef('TRC_START_TIME')
            ).values('SHF_CODE')[:1]
        ))
        .values('date', 'shift')
        .distinct()
        .order_by('-date')
    )
    date_shift_choices = [
        {
            'value': f"{item['date']}|{item['shift']}",
            'label': f"{item['date'].strftime('%d/%m/%Y')} - {item['shift']}"
        }
        for item in date_shift_raw if item['shift']
    ]


    # -------------- LINE TRACEABILITY BY MATERIALS + CHILDS -----------------
    traceability_raw = []

    if start_date and end_date:
        mat_code_subquery = MD_MATERIALS.objects.filter(
            MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')
        ).values('MAT_CODE')[:1]

        wm_name_subquery = MD_WORKERS.objects.filter(
            WM_CODE=OuterRef('TRC_WM_CODE')
        ).values('WM_NAME')[:1]

        traceability_qs = WMS_TRACEABILITY.objects.filter(
            TRC_START_TIME__date__range=(start_date, end_date),
            TRC_SFC_CODE__in=allowed_sfc_code
        ).annotate(

            MAT_CODE=Subquery(mat_code_subquery),
            WM_NAME=Subquery(wm_name_subquery),
        )

        if sfc_code:
            traceability_qs = traceability_qs.filter(TRC_SFC_CODE=sfc_code)

        if mat_code:
            traceability_qs = traceability_qs.filter(TRC_MAT_SAP_CODE=mat_code)

        if trc_fl_phase:
            traceability_qs = traceability_qs.filter(TRC_FL_PHASE=trc_fl_phase)

        traceability_raw = list(
            traceability_qs.values(
                'TRC_PP_CODE',
                'TRC_MCH_CODE',
                'TRC_SO_CODE',
                'TRC_SFC_CODE',
                'TRC_MAT_SAP_CODE',
                'TRC_WM_CODE',
                'TRC_START_TIME',
                'TRC_END_TIME',
                'TRC_CU_EXT_PROGR',
                'MAT_CODE',
                'WM_NAME',
            )
        )

    # ------------- CONTEXT KE HTML ---------------
    context = {
        'sfc_list': sfc_list,
        'material_list': material_list,
        'phase': phase,
        'traceability_raw': traceability_raw,
        'date_shift_choices': date_shift_choices,
        'selected_sfc': sfc_code,
        'selected_mat': mat_code,
        'selected_start_date': start_date_raw,
        'selected_end_date': end_date_raw,
        'selected_phase': trc_fl_phase,
    }

    return render(request, 'traceability_by_materials.html', context)