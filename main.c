/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : SMART BMS NODE - B?N FINAL HOÀN H?O (CALIBRATION + DELAY)
  * @author         : Nhóm Chu Ð?c Hi?u & Mai Ð?c H?i
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
// Ðã du?c tinh ch?nh chu?n xác, Cell 4 dã du?c cân b?ng
// ====================================================================
#define CAL_V1 4.76  // H? s? do Cell 1
#define CAL_V2 4.56  // ÐÃ GI?M XU?NG: Ép Cell 2 không b? v?ng lên
#define CAL_V3 4.53  // ÐÃ GI?M XU?NG: Tr? l?i qu? di?n áp cho Cell 4
#define CAL_V4 5.00  // H? s? T?ng áp (Gi? nguyên 5.00)

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
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET);
  /* USER CODE END 2 */

  /* Infinite loop */
  while (1)
  {
      // ====================================================================
      // BU?C 1: Ð?C CHI?T ÁP Ð? GI? L?P L?I T?T ÁP VÀ T?C Ð? XE
      // ====================================================================
      Potentiometer_Val = (ADC_Read_Channel(ADC_CHANNEL_6) / 4095.0) * 1.5;
      
      // Áp d?ng b? l?c nhi?u sâu (0.98) giúp s? li?u chi?t áp thay d?i c?c k? êm ái
      Smooth_Pot = (Smooth_Pot * 0.98) + (Potentiometer_Val * 0.02);
      Simulated_Speed = (uint8_t)((Smooth_Pot / 1.5) * 80.0);

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

      // ====================================================================
      // BU?C 3: NHÂN H? S? BÙ TR? SAI S? PH?N C?NG
      // ====================================================================
      V_Sens1 = ((sum_adc0 / 50.0) / 4095.0) * 3.3 * CAL_V1; 
      V_Sens2 = ((sum_adc1 / 50.0) / 4095.0) * 3.3 * CAL_V2;
      V_Sens3 = ((sum_adc2 / 50.0) / 4095.0) * 3.3 * CAL_V3;
      V_Sens4 = ((sum_adc3 / 50.0) / 4095.0) * 3.3 * CAL_V4;

      // ====================================================================
      // BU?C 4: TÍNH TOÁN ÐI?N ÁP T?NG CELL VÀ ÁP D?NG CHI?T ÁP VÀO CELL 1
      // ====================================================================
      Cell1 = V_Sens1 - Smooth_Pot; // Chi?t áp s? làm t?t di?n áp hi?n th? c?a Cell 1
      if(Cell1 < 0) Cell1 = 0.0; 
      
      Cell2 = V_Sens2 - V_Sens1;
      Cell3 = V_Sens3 - V_Sens2;
      Cell4 = V_Sens4 - V_Sens3; 
      Total_Voltage = V_Sens4;

      // ====================================================================
      // BU?C 5: Ð?C C?M BI?N & XU?T L?NH B?O V?
      // ====================================================================
      INA226_Read_Current();
      Read_Temperature_NTC();
      BMS_Protection_Logic();
      CAN_Send_Data();

      HAL_GPIO_TogglePin(GPIOC, GPIO_PIN_13); // Nháy LED trên m?ch
      
      // Delay 1.5 giây d? s? li?u hi?n ra ch?m, t? t? và d? quan sát
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
    uint8_t data[2];
    int16_t shunt_raw;

    HAL_I2C_Master_Transmit(&hi2c1, (0x40 << 1), &reg, 1, 10);
    HAL_I2C_Master_Receive(&hi2c1, (0x40 << 1), data, 2, 10);
    
    shunt_raw = (int16_t)((data[0] << 8) | data[1]);
    Current_Amps = shunt_raw * 0.00025;
}

void Read_Temperature_NTC(void)
{
    uint32_t adc_val = ADC_Read_Channel(ADC_CHANNEL_5);
    if(adc_val > 0 && adc_val < 4095) {
        float R_NTC = 10000.0 * ((float)adc_val / (4095.0 - (float)adc_val));
        float Temp_Kelvin = 1.0 / (1.0 / 298.15 + (1.0 / 3950.0) * log(R_NTC / 10000.0));
        Battery_Temp = Temp_Kelvin - 273.15;
    } else {
        Battery_Temp = -99.0; 
    }
}

void BMS_Protection_Logic(void)
{
    Fault_Code = 0; 
    
    // B?o v? T?t áp và Quá áp
    if(Cell1 < 3.0 || Cell2 < 3.0 || Cell3 < 3.0 || Cell4 < 3.0) {
        Fault_Code = 1; 
    }
    else if(Cell1 > 4.25 || Cell2 > 4.25 || Cell3 > 4.25 || Cell4 > 4.25) {
        Fault_Code = 4;
    }
    else if(Current_Amps > 10.0 || Current_Amps < -10.0) {
        Fault_Code = 2; 
    }
    else if(Battery_Temp > 55.0) {
        Fault_Code = 3; 
    }

    // Ði?u khi?n Ro-le (Ðã d?o Logic cho chân H)
    if(Fault_Code != 0) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_RESET); // L?i -> C?t di?n (M?c LOW 0V t?t tuy?t d?i)
    } else {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET);   // OK -> Ðóng di?n (M?c HIGH 3.3V)
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
    CAN_TxHeaderTypeDef TxHeader;
    uint32_t TxMailbox;
    uint8_t TxData[8];

    TxHeader.IDE = CAN_ID_STD;
    TxHeader.RTR = CAN_RTR_DATA;
    TxHeader.DLC = 8; 

    // Gói 1: T?ng áp, Dòng di?n, Cell 1, Cell 2
    TxHeader.StdId = 0x103; 
    uint16_t t_vol = (uint16_t)(Total_Voltage * 100);
    int16_t t_cur = (int16_t)(Current_Amps * 100);
    uint16_t c1 = (uint16_t)(Cell1 * 100);
    uint16_t c2 = (uint16_t)(Cell2 * 100);

    TxData[0] = (t_vol >> 8) & 0xFF; TxData[1] = t_vol & 0xFF;
    TxData[2] = (t_cur >> 8) & 0xFF; TxData[3] = t_cur & 0xFF;
    TxData[4] = (c1 >> 8) & 0xFF;    TxData[5] = c1 & 0xFF;
    TxData[6] = (c2 >> 8) & 0xFF;    TxData[7] = c2 & 0xFF;
    
    HAL_CAN_AddTxMessage(&hcan, &TxHeader, TxData, &TxMailbox);
    
    // Gói 2: Cell 3, Cell 4, Nhi?t d?, Mã L?i, T?c d?
    TxHeader.StdId = 0x104; 
    uint16_t c3 = (uint16_t)(Cell3 * 100);
    uint16_t c4 = (uint16_t)(Cell4 * 100);
    int16_t temp = (int16_t)(Battery_Temp * 100); 

    TxData[0] = (c3 >> 8) & 0xFF;    TxData[1] = c3 & 0xFF;
    TxData[2] = (c4 >> 8) & 0xFF;    TxData[3] = c4 & 0xFF;
    TxData[4] = (temp >> 8) & 0xFF;  TxData[5] = temp & 0xFF;
    TxData[6] = Fault_Code;          
    TxData[7] = Simulated_Speed;     
    
    HAL_CAN_AddTxMessage(&hcan, &TxHeader, TxData, &TxMailbox);
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
  HAL_RCC_OscConfig(&RCC_OscInitStruct);

  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;
  HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2);
}

void Error_Handler(void)
{
  __disable_irq();
  while (1) {}
}

#ifdef  USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line) {}
#endif