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

























# ============== Traceability By Machine ===============
def traceability_by_machine(request):
    trc_code = request.GET.get('trc_code')
    mch_info = request.GET.get('mch_info')
    start_date_raw = request.GET.get('start_date')
    end_date_raw = request.GET.get('end_date')
    trc_fl_phase = request.GET.get('trc_fl_phase')

    def parse_date_shift(raw_value):
        try:
            date_part, shift_part = raw_value.split('|')
            return date_part, shift_part
        except:
            return None, None

    # Tanggal dan Shift
    start_date, _ = parse_date_shift(start_date_raw)
    end_date, _ = parse_date_shift(end_date_raw)
    try:
        if start_date and end_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        else:
            start_date = end_date = None
    except ValueError:
        start_date = end_date = None

    # Ambil production phase
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

    machines = []
    if trc_code:
        machines = (
            WMS_TRACEABILITY.objects
            .filter(TRC_PP_CODE=trc_code)
            .values('TRC_PP_CODE', 'TRC_MCH_CODE')
            .distinct()
            .order_by('TRC_MCH_CODE')
    )

    phase = (
        WMS_TRACEABILITY.objects
        .values('TRC_FL_PHASE')
        .distinct()
        .order_by('TRC_FL_PHASE')
    )

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
        {'value': f"{d['date']}|{d['shift']}", 'label': f"{d['date'].strftime('%d/%m/%Y')} - {d['shift']}"}
        for d in date_shift_raw if d['shift']
    ]

    # ========Filter traceability (pengambilan data yang terfilter)=========
    traceability_raw = []
    if trc_code and mch_info and start_date and end_date and trc_fl_phase:
        traceability_qs = WMS_TRACEABILITY.objects.filter(
            TRC_START_TIME__date__range=(start_date, end_date)
        ).annotate(
            MAT_CODE=Subquery(
                MD_MATERIALS.objects.filter(
                    MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')
                ).values('MAT_CODE')[:1]
            ),
            WM_CODE=Subquery(
                MD_WORKERS.objects.filter(
                    WM_CODE=OuterRef('TRC_WM_CODE')
                ).values('WM_CODE')[:1]
            ),
            WM_NAME=Subquery(
                MD_WORKERS.objects.filter(
                    WM_CODE=OuterRef('TRC_WM_CODE')
                ).values('WM_NAME')[:1]
            )
        )
        if trc_code:
            traceability_qs = traceability_qs.filter(TRC_PP_CODE=trc_code)
        if trc_fl_phase:
            traceability_qs = traceability_qs.filter(TRC_FL_PHASE=trc_fl_phase)
        if mch_info:
            try:
                trc_pp, trc_mch = mch_info.split('|')
                traceability_qs = traceability_qs.filter(
                    TRC_PP_CODE=trc_pp, TRC_MCH_CODE=trc_mch
                )
            except ValueError:
                pass

        traceability_raw = list(traceability_qs.values(
            'TRC_PP_CODE', 'TRC_MCH_CODE', 'TRC_SO_CODE', 'TRC_MAT_SAP_CODE',
            'TRC_WM_CODE', 'TRC_START_TIME', 'TRC_END_TIME', 'TRC_CU_EXT_PROGR',
            'MAT_CODE', 'WM_CODE', 'WM_NAME'
        ))

    # Fungsi bantu
    def get_pp_mch_wm_from_cu(cu_ext_progr):
        info = WMS_TRACEABILITY_CU.objects.filter(
            CU_EXT_PROGR=cu_ext_progr
        ).values('PP_CODE', 'MCH_CODE', 'WM_CODE').first()
        return info or {'PP_CODE': '', 'MCH_CODE':  '', 'WM_CODE': ''}

    def get_worker_name(wm_code):
        if not wm_code:
            return ''
        worker = MD_WORKERS.objects.filter(WM_CODE=wm_code).values('WM_NAME').first()
        return worker['WM_NAME'] if worker else ''

    def get_child_cu_tree(parent_cu, level=1):
        child_data = []
        # Cari semua anak yang ada di CHILD_CU_EXT_PROGR di record induk CU_EXT_PROGR = parent_cu
        parent_records = WMS_TRACEABILITY_CU.objects.filter(CU_EXT_PROGR=parent_cu)

        for parent_rec in parent_records:
            child_cu = parent_rec.CHILD_CU_EXT_PROGR
            if not child_cu:
                continue

            info = get_pp_mch_wm_from_cu(child_cu)
            operator = {'WM_CODE': info['WM_CODE'], 'WM_NAME': get_worker_name(info['WM_CODE'])}

            detail = WMS_TRACEABILITY.objects.filter(
                TRC_CU_EXT_PROGR=child_cu
            ).annotate(
                MAT_CODE=Subquery(
                    MD_MATERIALS.objects.filter(
                        MAT_SAP_CODE=OuterRef('TRC_MAT_SAP_CODE')
                    ).values('MAT_CODE')[:1]
                )
            ).values(
                'TRC_PP_CODE','TRC_MCH_CODE','TRC_SO_CODE',
                'TRC_MAT_SAP_CODE','TRC_WM_CODE','TRC_START_TIME',
                'TRC_END_TIME','TRC_CU_EXT_PROGR','MAT_CODE'
            ).first()

            if detail:
                detail.update({
                    'level': level,
                    'type': 'child',
                    'OPERATOR_PROD': operator,
                })
                child_data.append(detail)

                # Search child from child
                child_data += get_child_cu_tree(child_cu, level + 1)
        return child_data

    traceability_tree = []
    for item in traceability_raw:
        info = get_pp_mch_wm_from_cu(item['TRC_CU_EXT_PROGR'])
        operator = {'WM_CODE': info['WM_CODE'], 'WM_NAME': get_worker_name(info['WM_CODE'])}

        root_node = {
            'type': 'root',
            'level': 0,
            **item,
            'OPERATOR_PROD': operator,
        }
        traceability_tree.append(root_node)
        traceability_tree += get_child_cu_tree(item['TRC_CU_EXT_PROGR'], 1)

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
        ).values('SO_CODE', 'CU_EXT_PROGR')

        cu_map = {}
        for cu in cu_data:
            key = (cu['SO_CODE'], cu['CU_EXT_PROGR'])
            cu_map.setdefault(key, []).append(cu['CHILD_SO_CODE', 'CHILD_CU_EXT_PROGR'])

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