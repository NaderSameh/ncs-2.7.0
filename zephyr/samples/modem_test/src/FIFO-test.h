// #ifndef FIFO_H
#define FIFOH_H

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define MQTT_QUEUE_SIZE 16

#define Tag_ID_Length (uint8_t)18
#define Number_Of_Tags_Per_CyTrack (uint8_t)10

// struct device *rtc;
// Enums for message types
typedef enum {
  Msg_Type_CyTag = 0x01,
  Msg_Type_GPS = 0x02,
  Msg_Type_LBS = 0x03,
  Msg_Type_Battery = 0x04,
  Msg_Type_Tamper = 0x05,
  Msg_Type_Undetected_Tag = 0x06,
  Msg_Type_Lock_Feedback = 0x07,
  Msg_Type_ICCID = 0x08,
  Msg_Type_Cellular_Rssi = 0x09,
  Msg_Type_Satcom_Rssi = 0x0A,
  Msg_Type_Jamming = 0x0B,
  Msg_Type_CHRG = 0x0C,
  Msg_Type_ACC = 0x0D,
  Msg_Type_SUB_RECV = 0x0E,
  Msg_Type_MOTION = 0x0F,
  Msg_Type_Mount = 0x10,
  Msg_Type_FMC225 = 0x11
} EN_msgType_t;

// Enums for id types
typedef enum {
  Id_Type_CyLock = 0x01,
  Id_Type_CyTrack = 0x02,
  Id_Type_CyTag = 0x03,
  Id_Type_CyBand = 0x04,
  Id_Type_CyConnect = 0x05
} EN_idType_t;

/****CyTag Event****/
// All bits equal to 0 -> No event
// Bit 0: Temperature Event
// Bit 1: Humididty Event
// Bit 2: Light Event
// Bit 3: In Contact
// Bit 4: Out of Contact

// Macro to set a specific bit in a variable
#define SET_BIT(var, bit) ((var) |= (1 << (bit)))

// Macro to clear a specific bit in a variable
#define CLEAR_BIT(var, bit) ((var) &= ~(1 << (bit)))

// Size of the whole ST_message_t structure is 250 Bytes.
// Fifo Elements is 16. 16*250+5 = 4,005 bytes which can fit in a sector. Sector
// size is 4096 bytes. We store in 375 sectores. 375 * 16 = 6000 messages.

// typedef struct ST_message_t {
//   EN_msgType_t msgType;
//   EN_idType_t idType;
//   char msg[238];
//   unsigned long timeStamp;
// } __attribute__((packed)) ST_message_t;

// FIFO structure
// typedef struct ST_Fifo_t {
//   uint16_t StartPtr; // Pointer to oldest entry or EndPtr if empty
//   uint16_t EndPtr;   // Pointer to next empty place to store a new entry
//   uint8_t noElements;
//   ST_message_t myMsgStruct[MQTT_QUEUE_SIZE];
// } __attribute__((packed)) ST_Fifo_t;

typedef struct {
  char Ble_CyTag_Ids[Number_Of_Tags_Per_CyTrack][Tag_ID_Length];
  uint8_t Skip_Count[Number_Of_Tags_Per_CyTrack];
} __attribute__((packed)) Tags_Info;

typedef struct {
  uint8_t Assigned_Tags_Count;
  Tags_Info Tags_Info;
} __attribute__((packed)) Assigned_Tags;

// void fifoInit(void);
// int8_t fifoPush(ST_message_t *msg);
// uint16_t fifoPull(char *str);

// Assigned_Tags my_Tags;

// unsigned long get_unix_ts(void){
//     return (unsigned long)10101010101;
// }

// #endif
