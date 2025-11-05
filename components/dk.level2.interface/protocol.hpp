
#include <cstring>

using namespace std;

#pragma pack(push, 1)
struct _type_dk_lv2_mf_instruction {
    char cTcCode[4];        /* TC Code */
    char cDate[14];         /* 송신시간 */
    char cTcLength[6];      /* 전문길이 */
    char cLotNo[15];        /* Lot No. */
    char cMtNo[15];         /* 강편번호 */
    char cTypeCode[6];      /* 소재규격명 */
    char cOrderLen[6];      /* 소재이론길이 */
    char cOrderWei[5];      /* 소재이론중량 */
    char cMtTypeCd[2];      /* 제품형태 */
    char cMtStand[30];      /* 제품규격명 */
    char cMtStGrad[16];     /* 제품강종 */
    char cMtSpecCd[30];     /* 제품규격약호 */
    char cMtLength[6];      /* 제품길이 */
    char cRfChaTem[4];      /* FM후면온도 */
    char cRfTime[6];        /* 재로시간 */
    char cBdTime[6];        /* BD 압연시간 */
    char cFMSpeed[4];       /* FM 10열 속도 */
    char cSacsUseM[1];      /* SACS 사용 */
    char cChargeIn[1];      /* Charge 정보 */
    char cTopCropLen[4];    /* 선단 Crop 길이 */
    char cBtmCropLen[4];    /* 후단 Crop 길이 */
    char cNomalH[4];        /* 호칭치수 H */
    char cNomalB[4];        /* 호칭치수 B */
    char cStandSize1[4];    /* 표준단면 치수(HB : H,  Angles : A, Chanel : H, SY : W) */
    char cStandSize2[4];    /* 표준단면 치수(HB : B,  Angles : B,  Chanel : B, SY : H) */
    char cStandSize3[3];    /* 표준단면 치수(HB : t1, Angles : tA, Chanel : t1, SY : tw) */
    char cStandSize4[3];    /* 표준단면 치수(HB : t2, Angles : tB, Chanel : t2, SY : tf) */
    char cStandSize5[3];    /* 표준단면 치수(HB : r1, Angles : r1, Chanel : r1) */
    char cStandSize6[3];    /* 표준단면 치수(HB : r2, Angles : r2, Chanel : r2) */
    char cDSCutCoun[1];     /* DS Number of cutting */
    char cFMLength[6];      /* 이론 FM 길이 */
    char cSpare[292];       /* Reserved */
};
#pragma pack(pop)
typedef _type_dk_lv2_mf_instruction dk_lv2_mf_instruction;

#pragma pack(push, 1)
struct _type_dk_lv2_mf_clear {
    char cTcCode[4];    /* TC Code */
    char cDate[14];     /* 송신시간 */
    char cTcLength[6];  /* 전문길이 */
    char cSpare[26];    /* 스페어 */
};
#pragma pack(pop)
typedef _type_dk_lv2_mf_clear dk_lv2_mf_clear;

#pragma pack(push, 1)
struct _type_dk_lv2_mf_alive {
    char cTcCode[4];    /* TC Code */
    char cDate[14];     /* 송신시간 */
    char cTcLength[6];  /* 전문길이 */
    char cCount[4];     /* 카운트 */
    char cSpare[22];    /* 스페어 */
};
#pragma pack(pop)
typedef _type_dk_lv2_mf_alive dk_lv2_mf_alive;

#pragma pack(push, 1)
struct _type_dk_sdd_defect {
    char cResult_Code[6];
    char cResult_Pos[6];
};
#pragma pack(pop)
typedef _type_dk_sdd_defect dk_sdd_defect;

#define MAX_RST_SIZE    60
#pragma pack(push, 1)
struct _type_dk_sdd_job_result {
    char cTcCode[4];        /* TC Code */
    char cDate[14];         /* 송신시간 */
    char cTcLength[6];      /* 전문길이 */
    char cLotNo[15];        /* Lot No */
    char cMtNo[15];         /* 강편번호 */
    char cMtTypeCd[2];      /* 제품형태 */
    char cMtStand[30];      /* 제품규격명 */
    char cCount[4];         /* Data Count */
    dk_sdd_defect cRst[MAX_RST_SIZE]; /* 결함 종류, 위치 정보 */
};
#pragma pack(pop)
typedef _type_dk_sdd_job_result dk_sdd_job_result;

#pragma pack(push, 1)
struct _type_dk_sdd_alarm {
    char cTcCode[4];    /* TC Code */
    char cDate[14];     /* 송신시간 */
    char cTcLength[6];  /* 전문길이 */
    char cMessage[3];   /* 알람메시지번호 */
    char cSpare[23];    /* 스페어 */
};
#pragma pack(pop)
typedef _type_dk_sdd_alarm dk_sdd_alarm;

#pragma pack(push, 1)
struct _type_dk_sdd_alive {
    char cTcCode[4];    /* TC Code */
    char cDate[14];     /* 송신시간 */
    char cTcLength[6];  /* 전문길이 */
    char cCount[4];     /* 카운트 */
    char cSpare[22];    /* 스페어 */
};
#pragma pack(pop)
typedef _type_dk_sdd_alive  dk_sdd_alive;

#pragma pack(push, 1)
struct _type_dk_h_standard_dim {
    int height;
    int width;
    double t1;  //web thickness
    double t2;  //flange thickness
};
#pragma pack(pop)
typedef _type_dk_h_standard_dim dk_h_standard_dim;

/* (added 25.11.04) sdd complete */
#pragma pack(push, 1)
struct _type_dk_sdd_job_complete {
    char cTcCode[4];    /* TC Code */
    char cDate[14];     /* 송신시간 */
    char cTcLength[6];  /* 전문길이 */
    char cLotNo[15];    /* Lot No */
    char cMtNo[15];     /* 강편번호 */
    char cMtTypeCd[2];  /* 제품형태 */
    char cMtStand[30];  /* 제품규격명 */
    char cCount[5];     /* 전체 획득 이미지 수*/
    char cSpare[10];    /* reserved */
};
#pragma pack(pop)
typedef _type_dk_sdd_job_complete dk_sdd_job_complete;

/* (added 25. 11. 04) lv2 defect labeled */
#pragma pack(push, 1)
struct _type_dk_lv2_defect_labeled {
    char cTcCode[4];        /* TC Code */
    char cDate[14];         /* 송신시간 */
    char cTcLength[6];      /* 전문길이 */
    char cMtNo[15];        /* 강편번호 */
    char cMea_Image1[50];   /* 측정 이미지 1 파일명 */
    char cMea_Image2[50];   /* 측정 이미지 2 파일명 */
    char cMea_Image3[50];   /* 측정 이미지 3 파일명 */
    char cMea_Image4[50];   /* 측정 이미지 4 파일명 */
    char cMea_Image5[50];   /* 측정 이미지 5 파일명 */
    char cMea_Image6[50];   /* 측정 이미지 6 파일명 */
    char cMea_Image7[50];   /* 측정 이미지 7 파일명 */
    char cMea_Image8[50];   /* 측정 이미지 8 파일명 */
    char cMea_Image9[50];   /* 측정 이미지 9 파일명 */
    char cMea_Image10[50];  /* 측정 이미지 10 파일명 */
    char cMea_Image11[50];  /* 측정 이미지 11 파일명 */
    char cMea_Image12[50];  /* 측정 이미지 12 파일명 */
    char cMea_Image13[50];  /* 측정 이미지 13 파일명 */
    char cMea_Image14[50];  /* 측정 이미지 14 파일명 */
    char cMea_Image15[50];  /* 측정 이미지 15 파일명 */
    char cSpare[11];      /* reserved */
};
#pragma pack(pop)
typedef _type_dk_lv2_defect_labeled dk_lv2_defect_labeled;