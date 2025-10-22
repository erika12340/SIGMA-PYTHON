from django.db import models

# -------------- 1. MD_SEMI+FINISHED_CLASSES ------------
class MD_SEMI_FINISHED_CLASSES(models.Model):
    SFC_CODE = models.CharField(max_length=9, primary_key=True)
    SFC_DESC = models.CharField(max_length=3)

    class Meta:
        db_table = 'MD_SEMI_FINISHED_CLASSES'
        managed = False

    def __str__(self):
        return f"{self.SFC_CODE} - {self.SFC_DESC}"

# -------------- 2. MD_MATERIALS -------------
class MD_MATERIALS(models.Model):
    MAT_SAP_CODE = models.CharField(max_length=9, primary_key=True)
    MAT_VARIANT = models.CharField(max_length=10)
    CNT_CODE = models.CharField(max_length=3)
    MAT_CODE = models.CharField(max_length=50)
    MAT_DESC = models.CharField(max_length=100)
    MAT_SPEC_CODE = models.CharField(max_length=10)
    MAT_MEASURE_UNIT = models.CharField(max_length=10)
    SFC_CODE = models.ForeignKey('MD_SEMI_FINISHED_CLASSES', db_column='SFC_CODE', on_delete=models.SET_NULL, null=True)

    class Meta:
        managed = False
        db_table = 'MD_MATERIALS'
        unique_together = (
            ('MAT_SAP_CODE', 'MAT_VARIANT', 'CNT_CODE'),
        )

# -------------- 3. MD_BOM --------------
class MD_BOM(models.Model):
    MAT_SAP_CODE = models.CharField(max_length=9, primary_key=True)
    MAT_VARIANT = models.CharField(max_length=10)
    CNT_CODE = models.CharField(max_length=3)
    LMM_SEQUENCE = models.IntegerField()
    MT_CODE = models.CharField(max_length=8)
    BV_STATUS = models.CharField(max_length=5)
    CHILD_MAT_VARIANT = models.CharField(max_length=10, null=True)
    CHILD_MAT_SAP_CODE = models.CharField(max_length=9, null=True)
    CHILD_CNT_CODE = models.CharField(max_length=3, null=True)
    BOM_QUANTITY = models.CharField(max_length=15)

    class Meta:
        managed = False
        db_table = 'MD_BOM'
        unique_together = (
            ('MAT_SAP_CODE', 'MAT_VARIANT', 'CNT_CODE'),
        )


# -------------- 4. DC_PRODUCTION_DATA --------------
class DC_PRODUCTION_DATA(models.Model):
    MAT_SAP_CODE = models.CharField(max_length=9, primary_key=True)
    PP_CODE = models.CharField(max_length=3)
    MCH_CODE = models.CharField(max_length=8)
    SHF_CODE = models.CharField(max_length=10)
    PS_QUANTITY = models.CharField(max_length=8)
    PS_DECLARE_SEC = models.CharField(max_length=8)
    PS_START_PROD = models.DateTimeField(max_length=8)
    PS_END_PROD = models.DateTimeField(max_length=8)
    PS_DATE = models.DateTimeField(max_length=8)
    CNT_CODE = models.CharField(max_length=3)
    MAT_VARIANT = models.CharField(max_length=10)

    class Meta:
        managed = False
        db_table = 'DC_PRODUCTION_DATA'
        unique_together = (
            ('MAT_SAP_CODE', 'MAT_VARIANT', 'CNT_CODE'),
        )



# -------------- Model 5. MD_PRODUCTION_PHASES -------------- 
class MD_PRODUCTION_PHASES(models.Model):
    PP_CODE = models.CharField(max_length=3, primary_key=True)
    PP_DESC = models.CharField(max_length=8)

    class Meta:
        managed = False
        db_table = 'MD_PRODUCTION_PHASES'

# -------------- 6. Model MD_WORKERS --------------
class MD_WORKERS(models.Model):
    WM_CODE = models.CharField(max_length=9, primary_key=True)
    WM_NAME = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'MD_WORKERS'

# -------------- 7. Model WMS_TRACEABILITY --------------
class WMS_TRACEABILITY(models.Model):
    TRC_PP_CODE = models.CharField (max_length=3, primary_key=True)
    TRC_MCH_CODE = models.CharField (max_length=8)
    TRC_SO_CODE = models.CharField (max_length=4)
    TRC_CU_EXT_PROGR = models.CharField (max_length=6)
    TRC_START_TIME = models.DateTimeField(max_length=8)
    TRC_END_TIME = models.DateTimeField (max_length=8)
    TRC_MAT_SAP_CODE = models.CharField (max_length=9)
    TRC_WM_CODE = models.CharField (max_length=8)
    TRC_FL_PHASE = models.CharField (max_length=1)
    TRC_CNT_CODE = models.CharField (max_length=3)
    TRC_MAT_VARIANT = models.CharField (max_length=10)

    class Meta:
        managed = False
        db_table = 'WMS_TRACEABILITY'
        unique_together = (
            ('TRC_PP_CODE', 'TRC_MCH_CODE','TRC_SO_CODE','TRC_CU_EXT_PROGR', 'TRC_START_TIME'),
        )

# -------------- 8. Model WMS_TRACEABILITY_CU (CHILD DARI TRACEABILITY) --------------
class WMS_TRACEABILITY_CU(models.Model):
    SO_CODE = models.CharField (max_length=4, primary_key=True)
    CU_EXT_PROGR = models.CharField (max_length=6)
    CHILD_CU_CODE = models.CharField (max_length=20)
    CHILD_SO_CODE = models.CharField (max_length=4)
    CHILD_CU_EXT_PROGR = models.CharField (max_length=6)

    class Meta:
        managed = False
        db_table = 'WMS_TRACEABILITY_CU'
        unique_together = (
            ('SO_CODE', 'CHILD_CU_CODE', 'CU_EXT_PROGR')
        )

# -------------- 9. Model MD_SOURCES --------------
class MD_SOURCES(models.Model):
    SO_CODE = models.CharField (max_length=4, primary_key=True)
    SO_DESC = models.CharField (max_length=30)

    class Meta:
        managed = False
        db_table = 'MD_SOURCES'