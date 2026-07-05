/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : SMART BMS NODE V_FINAL (Ð?NG B? 100% T? B?N KEIL C CHU?N)
  * @author         : K? su H? th?ng Ði?n & Ô tô
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "adc.h"
#include "can.h"
#include "i2c.h"
#include "gpio.h"
#include <stdio.h>
#include <math.h>

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
// ====================================================================
// KHU V?C ÐI?U CH?NH SAI S? (CALIBRATION) 
// ====================================================================
#define CAL_V1 5.46  // Kéo Cell 1 lên m?c chu?n (dã c?ng hao phí chi?t áp)
#define CAL_V2 5.15  // Cân b?ng cho Cell 2
#define CAL_V3 5.06  // Tr? l?i d? chu?n cho V_Sens3, tri?t tiêu l?i v?ng c?a Cell 4
#define CAL_V4 5.03  // Tinh ch?nh t?ng áp h? th?ng
/* USER CODE END PD */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN PV */
// --- Bi?n luu tr? Ði?n áp ---
float V_Sens1, V_Sens2, V_Sens3, V_Sens4; 
float Cell1, Cell2, Cell3, Cell4;         
float Total_Voltage = 0;

// --- Bi?n Dòng di?n & Nhi?t d? ---
float Current_Amps = 0;
float Battery_Temp = 0; 

// --- SOC Variables ---
float SOC_Percent = 100.0f; 
float Avg_Cell_V_Filtered = 0.0f;
#define BATTERY_CAPACITY_AH 10.0f


// --- Bi?n Gi? l?p & Tr?ng thái ---
float Potentiometer_Val = 0; 
float Smooth_Pot = 0;        
uint8_t Simulated_Speed = 0; 
uint8_t Fault_Code = 0; // 0: OK | 1: T?t áp | 2: Quá dòng | 3: Quá nhi?t | 4: Quá áp
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
uint32_t ADC_Read_Channel(uint32_t Channel);
void INA226_Init(void);
void INA226_Read_Current(void);
void Read_Temperature_NTC(void);
void BMS_Protection_Logic(void);
void CAN_Filter_Config(void);
void CAN_Send_Data(void);
float SOC_OCV_Lookup(float voltage);
/* USER CODE END PFP */

int main(void)
{
  HAL_Init();
  SystemClock_Config();
  MX_GPIO_Init();
  MX_ADC1_Init();
  MX_CAN_Init();
  MX_I2C1_Init();

  /* USER CODE BEGIN 2 */
  CAN_Filter_Config();
  HAL_CAN_Start(&hcan);
  INA226_Init();

  // Ð?i thành SET: M?c d?nh xu?t m?c CAO (1) ra chân PA4 d? ÐÓNG ro-le (Ch? d? High-Trigger)
  // Xóa dòng này n?u mô-to d?-ba quá m?nh làm s?p ngu?n chip
  // HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET); 
  /* USER CODE END 2 */

  /* Infinite loop */
  while (1)
  {
      // ====================================================================
      // BU?C 1: Ð?C CHI?T ÁP T? CHÂN PA6 VÀ L?C NHI?U MU?T MÀ
      // ====================================================================
     // ====================================================================
      // BU?C 1: Ð?C CHI?T ÁP T? CHÂN PA6 (ÐÃ TANG Ð? NH?Y VÀ BIÊN Ð?)
      // ====================================================================
      // 1. Tang h? s? t? 1.5 lên 2.5: V?n h?t c? s? kéo t?t du?c t?n 2.5V (T?t c?c nhanh)
      Potentiometer_Val = (ADC_Read_Channel(ADC_CHANNEL_6) / 4095.0) * 2.5;
      
      // 2. N?i l?ng b? l?c: Gi?m t? 0.98 xu?ng 0.85. 
      // (Nh?n 15% s? thay d?i ngay l?p t?c thay vì 2% nhu cu -> H?t b? tr?)
      Smooth_Pot = (Smooth_Pot * 0.85) + (Potentiometer_Val * 0.15);
      
      // 3. Ð?ng b? l?i kim d?ng h? t?c d? v?i d?i 2.5V m?i
      Simulated_Speed = (uint8_t)((Smooth_Pot / 2.5) * 80.0);

      // ====================================================================
      // BU?C 2: Ð?C ÐI?N ÁP 4 KÊNH ADC (L?y m?u 50 l?n ch?ng nhi?u)
      // ====================================================================
      uint32_t sum_adc0 = 0, sum_adc1 = 0, sum_adc2 = 0, sum_adc3 = 0;
      for(int i = 0; i < 50; i++) {
          sum_adc0 += ADC_Read_Channel(ADC_CHANNEL_0);
          sum_adc1 += ADC_Read_Channel(ADC_CHANNEL_1);
          sum_adc2 += ADC_Read_Channel(ADC_CHANNEL_2);
          sum_adc3 += ADC_Read_Channel(ADC_CHANNEL_3);
      }

      // Áp d?ng h? s? bù tr? sai s? ph?n c?ng
      V_Sens1 = ((sum_adc0 / 50.0) / 4095.0) * 3.3 * CAL_V1;
      V_Sens2 = ((sum_adc1 / 50.0) / 4095.0) * 3.3 * CAL_V2;
      V_Sens3 = ((sum_adc2 / 50.0) / 4095.0) * 3.3 * CAL_V3;
      V_Sens4 = ((sum_adc3 / 50.0) / 4095.0) * 3.3 * CAL_V4;

      // Tính di?n áp t?ng Cell riêng l?
      Cell1 = V_Sens1 - Smooth_Pot; 
      if(Cell1 < 0) Cell1 = 0.0;
      
      Cell2 = V_Sens2 - V_Sens1;
      Cell3 = V_Sens3 - V_Sens2;
      Cell4 = V_Sens4 - V_Sens3;
      Total_Voltage = V_Sens4;

      // ====================================================================
      // BU?C 3: Ð?C DÒNG ÐI?N VÀ NHI?T Ð?
      // ====================================================================
      INA226_Read_Current();
      Read_Temperature_NTC();

      // ====================================================================
      // BU?C 4: LOGIC B?O V? (QUY?T Ð?NH ÐÓNG/C?T RO-LE)
      // ====================================================================
      BMS_Protection_Logic();

      // --- HYBRID SOC ESTIMATION (Coulomb Counting + OCV) ---
      static uint32_t last_tick = 0;
      uint32_t current_tick = HAL_GetTick();
      if(last_tick == 0) last_tick = current_tick;
      float dt_hours = (current_tick - last_tick) / 3600000.0f;
      last_tick = current_tick;

      float avg_cell_v_raw = Total_Voltage / 4.0f;
      if (Avg_Cell_V_Filtered == 0.0f) {
          Avg_Cell_V_Filtered = avg_cell_v_raw;
      } else {
          Avg_Cell_V_Filtered = (Avg_Cell_V_Filtered * 0.9f) + (avg_cell_v_raw * 0.1f);
      }

      float processed_current = Current_Amps;
      static uint32_t idle_start_tick = 0;

      if (fabs(Current_Amps) < 0.1f) {
          processed_current = 0.0f; 
          
          if (Cell1 > 4.18f && Cell2 > 4.18f && Cell3 > 4.18f && Cell4 > 4.18f && fabs(Current_Amps) < 0.05f) {
              SOC_Percent = 100.0f;
          }

          if (idle_start_tick == 0) {
              idle_start_tick = current_tick;
          } else if ((current_tick - idle_start_tick) > 30000) {
              float ocv_soc = SOC_OCV_Lookup(Avg_Cell_V_Filtered);
              SOC_Percent = (SOC_Percent * 0.99f) + (ocv_soc * 0.01f);
          }
      } else {
          idle_start_tick = 0; 
      }

      SOC_Percent -= (processed_current * dt_hours / BATTERY_CAPACITY_AH) * 100.0f;

      if (SOC_Percent > 100.0f) SOC_Percent = 100.0f;
      if (SOC_Percent < 0.0f) SOC_Percent = 0.0f;

      // ====================================================================
      // BU?C 5: GÓI D? LI?U G?I SANG BEAGLEBONE (QUA CAN BUS)
      // ====================================================================
      CAN_Send_Data();

      HAL_GPIO_TogglePin(GPIOC, GPIO_PIN_13);
      
      // Delay 1.5 giây d? ?n d?nh ch?ng s?p ngu?n khi d?-ba
      HAL_Delay(1500);
  }
}

// ====================================================================
// CÁC HÀM C?U HÌNH VÀ GIAO TI?P
// ====================================================================

uint32_t ADC_Read_Channel(uint32_t Channel)
{
    ADC_ChannelConfTypeDef sConfig = {0};
    sConfig.Channel = Channel;
    sConfig.Rank = ADC_REGULAR_RANK_1;
    sConfig.SamplingTime = ADC_SAMPLETIME_71CYCLES_5;
    
    if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK) return 0;
    
    HAL_ADC_Start(&hadc1);
    HAL_ADC_PollForConversion(&hadc1, 10);
    uint32_t val = HAL_ADC_GetValue(&hadc1);
    HAL_ADC_Stop(&hadc1);
    return val;
}

void INA226_Init(void)
{
    uint8_t config_data[3] = {0x05, 0x0A, 0x00};
    HAL_I2C_Master_Transmit(&hi2c1, (0x40 << 1), config_data, 3, 100);
}

void INA226_Read_Current(void)
{
    uint8_t reg = 0x01;
    uint8_t data[2] = {0, 0};
    int16_t shunt_raw;

    HAL_I2C_Master_Transmit(&hi2c1, (0x40 << 1), &reg, 1, 10);
    if (HAL_I2C_Master_Receive(&hi2c1, (0x40 << 1), data, 2, 10) == HAL_OK) {
        shunt_raw = (int16_t)((data[0] << 8) | data[1]);
        float raw_current = shunt_raw * 0.00025f;
        
        static uint8_t first_read = 1;
        if (first_read) {
            Current_Amps = raw_current;
            first_read = 0;
        } else {
            Current_Amps = (Current_Amps * 0.8f) + (raw_current * 0.2f);
        }
    }
}

void Read_Temperature_NTC(void)
{
    float TEMP_OFFSET = -3.5; 
    static float Smooth_ADC_Temp = 0; 

    uint32_t sum_adc = 0;
    for(int i = 0; i < 50; i++) {
        sum_adc += ADC_Read_Channel(ADC_CHANNEL_5);
    }
    float current_adc = sum_adc / 50.0;

    if(Smooth_ADC_Temp == 0) Smooth_ADC_Temp = current_adc;

    Smooth_ADC_Temp = (Smooth_ADC_Temp * 0.95) + (current_adc * 0.05);

    if(Smooth_ADC_Temp > 0 && Smooth_ADC_Temp < 4095) {
        float R_NTC = 10000.0 * (Smooth_ADC_Temp / (4095.0 - Smooth_ADC_Temp));
        float Temp_Kelvin = 1.0 / (1.0 / 298.15 + (1.0 / 3950.0) * log(R_NTC / 10000.0));
        Battery_Temp = (Temp_Kelvin - 273.15) + TEMP_OFFSET;
    } else {
        Battery_Temp = -99.0; 
    }
}

void BMS_Protection_Logic(void)
{
    if(Cell1 < 3.0 || Cell2 < 3.0 || Cell3 < 3.0 || Cell4 < 3.0) {
        Fault_Code = 1; 
    }
    else if(Cell1 > 4.25 || Cell2 > 4.25 || Cell3 > 4.25 || Cell4 > 4.25) {
        Fault_Code = 4;
    }
    else if(Current_Amps > 15.0 || Current_Amps < -15.0) { 
        Fault_Code = 2; 
    }
    else if(Battery_Temp > 55.0) {
        Fault_Code = 3; 
    }

    if(Fault_Code == 1) {
        if(Cell1 > 3.05 && Cell2 > 3.05 && Cell3 > 3.05 && Cell4 > 3.05) Fault_Code = 0; 
    }
    else if(Fault_Code == 4) {
        if(Cell1 < 4.15 && Cell2 < 4.15 && Cell3 < 4.15 && Cell4 < 4.15) Fault_Code = 0;
    }
    else if(Fault_Code == 2) {
        if(Current_Amps > -2.0 && Current_Amps < 2.0) Fault_Code = 0;
    }
    else if(Fault_Code == 3) {
        if(Battery_Temp < 45.0) Fault_Code = 0;
    }

    if(Fault_Code != 0) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_RESET); // M?c LOW 0V ng?t an toàn
    } else {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET);   // M?c HIGH 3.3V dóng di?n
    }
}

void CAN_Filter_Config(void)
{
    CAN_FilterTypeDef canfilterconfig;
    canfilterconfig.FilterActivation = CAN_FILTER_ENABLE;
    canfilterconfig.FilterBank = 0;
    canfilterconfig.FilterFIFOAssignment = CAN_RX_FIFO0;
    canfilterconfig.FilterIdHigh = 0x0000;
    canfilterconfig.FilterIdLow = 0x0000;
    canfilterconfig.FilterMaskIdHigh = 0x0000;
    canfilterconfig.FilterMaskIdLow = 0x0000;
    canfilterconfig.FilterMode = CAN_FILTERMODE_IDMASK;
    canfilterconfig.FilterScale = CAN_FILTERSCALE_32BIT;
    HAL_CAN_ConfigFilter(&hcan, &canfilterconfig);
}

void CAN_Send_Data(void)
{
    // Kh?i t?o = {0} d? d?n s?ch rác trong b? nh?, ngan l?i tham s?
    CAN_TxHeaderTypeDef TxHeader = {0}; 
    uint32_t TxMailbox;
    uint8_t TxData[8];

    // =========================================================
    // CO CH? CH?NG K?T M?NG VÀ XÓA L?I 0x002
    // =========================================================
    if (HAL_CAN_GetTxMailboxesFreeLevel(&hcan) == 0) 
    {
        // Ép ph?n c?ng h?y b? các gói tin cu dang k?t ch? ACK
        HAL_CAN_AbortTxRequest(&hcan, CAN_TX_MAILBOX0 | CAN_TX_MAILBOX1 | CAN_TX_MAILBOX2);
        
        // Reset tr?c ti?p c? l?i d? Keil C không b? luu l?i l?i cu
        hcan.ErrorCode = 0; 
    }

    TxHeader.IDE = CAN_ID_STD;
    TxHeader.RTR = CAN_RTR_DATA;
    TxHeader.DLC = 8; 

    // ==========================================
    // GÓI 1 (Frame 0x103): T?ng Áp, Dòng Ði?n, Cell 1, Cell 2
    // ==========================================
    TxHeader.StdId = 0x103;
    uint16_t t_vol = (uint16_t)(Total_Voltage * 100);
    int16_t t_cur = (int16_t)(Current_Amps * 100);
    uint16_t c1 = (uint16_t)(Cell1 * 100);
    uint16_t c2 = (uint16_t)(Cell2 * 100);

    TxData[0] = (t_vol >> 8) & 0xFF; TxData[1] = t_vol & 0xFF;
    TxData[2] = (t_cur >> 8) & 0xFF; TxData[3] = t_cur & 0xFF;
    TxData[4] = (c1 >> 8) & 0xFF;    TxData[5] = c1 & 0xFF;
    TxData[6] = (c2 >> 8) & 0xFF;    TxData[7] = c2 & 0xFF;
    
    if (HAL_CAN_GetTxMailboxesFreeLevel(&hcan) > 0) 
    {
        HAL_CAN_AddTxMessage(&hcan, &TxHeader, TxData, &TxMailbox);
    }
    
    HAL_Delay(5); 

    // ==========================================
    // GÓI 2 (Frame 0x104): Cell 3, Cell 4, Nhi?t d?, Mã L?i
    // ==========================================
    TxHeader.StdId = 0x104;
    uint16_t c3 = (uint16_t)(Cell3 * 100);
    uint16_t c4 = (uint16_t)(Cell4 * 100);
    int16_t temp = (int16_t)(Battery_Temp * 100);
    
    TxData[0] = (c3 >> 8) & 0xFF;    TxData[1] = c3 & 0xFF;
    TxData[2] = (c4 >> 8) & 0xFF;    TxData[3] = c4 & 0xFF;
    TxData[4] = (temp >> 8) & 0xFF;  TxData[5] = temp & 0xFF;
    TxData[6] = Fault_Code;
    TxData[7] = (uint8_t)SOC_Percent; 
    
    if (HAL_CAN_GetTxMailboxesFreeLevel(&hcan) > 0) 
    {
        HAL_CAN_AddTxMessage(&hcan, &TxHeader, TxData, &TxMailbox);
    }
}

void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL9;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK) Error_Handler();

  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;
  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK) Error_Handler();
}

void Error_Handler(void)
{
  __disable_irq();
  while (1) {}
}

float SOC_OCV_Lookup(float voltage)
{
    if (voltage >= 4.20f) return 100.0f;
    else if (voltage >= 4.06f) return 90.0f + (voltage - 4.06f) / (4.20f - 4.06f) * 10.0f;
    else if (voltage >= 3.98f) return 80.0f + (voltage - 3.98f) / (4.06f - 3.98f) * 10.0f;
    else if (voltage >= 3.92f) return 70.0f + (voltage - 3.92f) / (3.98f - 3.92f) * 10.0f;
    else if (voltage >= 3.87f) return 60.0f + (voltage - 3.87f) / (3.92f - 3.87f) * 10.0f;
    else if (voltage >= 3.82f) return 50.0f + (voltage - 3.82f) / (3.87f - 3.82f) * 10.0f;
    else if (voltage >= 3.79f) return 40.0f + (voltage - 3.79f) / (3.82f - 3.79f) * 10.0f;
    else if (voltage >= 3.77f) return 30.0f + (voltage - 3.77f) / (3.79f - 3.77f) * 10.0f;
    else if (voltage >= 3.74f) return 20.0f + (voltage - 3.74f) / (3.77f - 3.74f) * 10.0f;
    else if (voltage >= 3.68f) return 10.0f + (voltage - 3.68f) / (3.74f - 3.68f) * 10.0f;
    else if (voltage >= 3.45f) return 5.0f + (voltage - 3.45f) / (3.68f - 3.45f) * 5.0f;
    else if (voltage >= 3.00f) return 0.0f + (voltage - 3.00f) / (3.45f - 3.00f) * 5.0f;
    else return 0.0f;
}

#ifdef  USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line) {}
#endif