
#include <cstring>

using namespace std;

struct dk_lv2_mf_instruction {
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
    char cSpare[298];       /* Reserved */

    void serialize(char* data, size_t size) const {
        std::memcpy(data, this, sizeof(dk_lv2_mf_instruction));
    }

    void deserialize(const char* data){
        std::memcpy(this, data, sizeof(dk_lv2_mf_instruction));
    }
};

struct dk_lv2_mf_clear {
    char cTcCode[4];    /* TC Code */
    char cDate[14];     /* 송신시간 */
    char cTcLength[6];  /* 전문길이 */
    char cSpare[26];    /* 스페어 */

    void serialize(char* data, size_t size) const {
        std::memcpy(data, this, sizeof(dk_lv2_mf_clear));
    }

    void deserialize(const char* data){
        std::memcpy(this, data, sizeof(dk_lv2_mf_clear));
    }
};


struct dk_lv2_mf_alive {
    char cTcCode[4];    /* TC Code */
    char cDate[14];     /* 송신시간 */
    char cTcLength[6];  /* 전문길이 */
    char cCount[4];     /* 카운트 */
    char cSpare[22];    /* 스페어 */

    void serialize(char* data, size_t size) const {
        std::memcpy(data, this, sizeof(dk_lv2_mf_clear));
    }

    void deserialize(const char* data){
        std::memcpy(this, data, sizeof(dk_lv2_mf_clear));
    }
};

struct dk_sdd_perform {
    char cTcCode[4];        /* TC Code */
    char cDate[14];         /* 송신시간 */
    char cTcLength[6];      /* 전문길이 */
    char cLotNo[15];        /* Lot No */
    char cMtNo[15];         /* 강편번호 */
    char cMtTypeCd[2];      /* 제품형태 */
    char cMtStand[30];      /* 제품규격명 */
    char cCount[4];         /* Data Count */
    char cResult1_Code[6];  /* 결함 측정1 Code */
    char cResult1_Pos[6];   /* 결함 측정1 위치 */
    char cResult2_Code[6];
    char cResult2_Pos[6];
    char cResult3_Code[6];
    char cResult3_Pos[6];
    char cResult4_Code[6];
    char cResult4_Pos[6];
    char cResult5_Code[6];
    char cResult5_Pos[6];
    char cResult6_Code[6];
    char cResult6_Pos[6];
    char cResult7_Code[6];
    char cResult7_Pos[6];;
    char cResult8_Code[6];
    char cResult8_Pos[6];
    char cResult9_Code[6];
    char cResult9_Pos[6];
    char cResult10_Code[6];
    char cResult10_Pos[6];

    void serialize(char* data, size_t size) const {
        std::memcpy(data, this, sizeof(dk_sdd_perform));
    }

    void deserialize(const char* data){
        std::memcpy(this, data, sizeof(dk_sdd_perform));
    }
};

struct _type_dk_sdd_alarm {
    char cTcCode[4];    /* TC Code */
    char cDate[14];     /* 송신시간 */
    char cTcLength[6];  /* 전문길이 */
    char cMessage[3];   /* 알람메시지번호 */
    char cSpare[23];    /* 스페어 */
};
typedef _type_dk_sdd_alarm dk_sdd_alarm;

struct _type_dk_sdd_alive {
    char cTcCode[4];    /* TC Code */
    char cDate[14];     /* 송신시간 */
    char cTcLength[6];  /* 전문길이 */
    char cCount[4];     /* 카운트 */
    char cSpare[22];    /* 스페어 */
};
typedef _type_dk_sdd_alive  dk_sdd_alive;