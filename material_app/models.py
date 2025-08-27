from django.db import models

# -------------- Model SF ------------
class MD_SEMI_FINISHED_CLASSES(models.Model):
    SFC_CODE = models.CharField(max_length=9, primary_key=True)
    SFC_DESC = models.CharField(max_length=3)

    class Meta:
        db_table = 'MD_SEMI_FINISHED_CLASSES'
        managed = False

    def __str__(self):
        return f"{self.SFC_CODE} - {self.SFC_DESC}"


# -------------- Model Material -------------
class MD_MATERIALS(models.Model):
    MAT_SAP_CODE = models.CharField(max_length=9, primary_key=True)
    MAT_VARIANT = models.CharField(max_length=10)
    CNT_CODE = models.CharField(max_length=3)
    MAT_CODE = models.CharField(max_length=50)
    MAT_DESC = models.CharField(max_length=100)
    MAT_IP_CODE = models.CharField(max_length=50)
    MAT_SPEC_CODE = models.CharField(max_length=10)
    MAT_MEASURE_UNIT = models.CharField(max_length=10)
    SFC_CODE = models.ForeignKey('MD_SEMI_FINISHED_CLASSES', db_column='SFC_CODE', on_delete=models.SET_NULL, null=True)
    MAT_MEASURE_UNIT = models.CharField(max_length=3)

    class Meta:
        managed = False
        db_table = 'MD_MATERIALS'
        unique_together = (
            ('MAT_SAP_CODE', 'MAT_VARIANT', 'CNT_CODE'),
        )


# -------------- Model BOM --------------
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


# -------------- Model Data Produksi --------------
class DC_PRODUCTION_DATA(models.Model):
    MAT_SAP_CODE = models.CharField(max_length=9, primary_key=True)
    PP_CODE = models.CharField(max_length=3)
    MCH_CODE = models.CharField(max_length=8)
    SHF_CODE = models.CharField(max_length=10)
    WM_CODE = models.CharField(max_length=8)
    PS_QUANTITY = models.CharField(max_length=8)
    PS_DECLARE_SEC = models.CharField(max_length=8)
    PS_START_PROD = models.DateTimeField(max_length=8)
    PS_DATE = models.DateTimeField(max_length=8)
    PS_END_PROD = models.DateTimeField(max_length=8)
    CNT_CODE = models.CharField(max_length=3)
    MAT_VARIANT = models.CharField(max_length=10)
    
    class Meta:
        managed = False
        db_table = 'DC_PRODUCTION_DATA'
        unique_together = (
            ('MAT_SAP_CODE', 'MAT_VARIANT', 'CNT_CODE'),
        )