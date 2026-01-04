#include "FIFO.h"
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(fifo, LOG_LEVEL_INF);

// Global FIFO instance
ST_Fifo_t myFifo;

// Stub functions for flash operations (to be implemented later)
static void writeFifoToFlash(void) {
  LOG_WRN("writeFifoToFlash: Not implemented, skipping flash write");
}

static void getFifoIndex(uint8_t *index) {
  *index = 0;
  LOG_WRN("getFifoIndex: Not implemented, returning 0");
}

static void importFifoFromFlash(void) {
  LOG_WRN("importFifoFromFlash: Not implemented, skipping flash import");
}

void trimJsonBraces(char *str) {
  // Simple implementation - remove first and last char if they're braces
  size_t len = strlen(str);
  if (len >= 2 && str[0] == '{' && str[len-1] == '}') {
    memmove(str, str + 1, len - 2);
    str[len - 2] = '\0';
  }
}

void removeFirstField(char *str) {
  // Find first comma and remove everything before it
  char *comma = strchr(str, ',');
  if (comma) {
    memmove(str, comma + 1, strlen(comma));
  }
}

void add_fields_to_json(char *json, const char *fields) {
  // Simple append with comma
  if (strlen(json) > 0 && json[strlen(json)-1] != ',') {
    strcat(json, ",");
  }
  strcat(json, fields);
}

void return_power_status(char *buffer, size_t size) {
  snprintf(buffer, size, "\"power\":\"OK\"");
}

// Initialize the FIFO structure
void fifoInit(void) {
  // Clear everything
  memset(&myFifo, 0, sizeof(myFifo));
  myFifo.noElements = 0;
}

int8_t fifoPush(ST_message_t *msg) {
  // Check if FIFO is full.
  if (myFifo.noElements >= MQTT_QUEUE_SIZE) {
    return -1; // FIFO is full.
  }

  bool duplicateFound = false;

  // Check for duplicate FMC messages (msgType == Msg_Type_FMC225).
  // It will only work if there was only one FMC.
  // There will be bug if more than one FMC is assigned because it doesn't check IMEI
  for (int i = 0; i < myFifo.noElements; i++) {
    if (  (myFifo.myMsgStruct[i].msgType == Msg_Type_FMC225 &&
            msg->msgType == Msg_Type_FMC225) && 
        (msg->timeStamp - myFifo.myMsgStruct[i].timeStamp < 300)) {

      strcpy(myFifo.myMsgStruct[i].msg, msg->msg); // Override message.
      myFifo.myMsgStruct[i].timeStamp = msg->timeStamp;

      printk("Duplicate FMC, Overriding\r\n");
      duplicateFound = true;

      return 0; // No need to push the new message.
    }

    if ((myFifo.myMsgStruct[i].msgType == 0x01 &&
         msg->msgType == 0x01 &&
        msg->device_index == myFifo.myMsgStruct[i].device_index) &&
        (msg->timeStamp - myFifo.myMsgStruct[i].timeStamp < 300)) {

        strcpy(myFifo.myMsgStruct[i].msg, msg->msg); // Override message.
        myFifo.myMsgStruct[i].timeStamp = msg->timeStamp;

        printk("Duplicate CyTag, Overriding\r\n");
        duplicateFound = true;

        return 0; // No need to push the new message.
    }
  }

  // No duplicate found, push the new message to FIFO.
  memcpy(&myFifo.myMsgStruct[myFifo.EndPtr], msg, sizeof(ST_message_t));
  myFifo.noElements++;

  // Wrap around the EndPtr if needed.
  myFifo.EndPtr = (myFifo.EndPtr + 1) % MQTT_QUEUE_SIZE;

  // Write to flash if FIFO is full.
  if (myFifo.noElements == MQTT_QUEUE_SIZE) {
    writeFifoToFlash();
  }

  return 0; // Successfully pushed the message.
}

uint16_t extractFromFifo(char *str) {
  if (myFifo.noElements == 0) {
    printk("Error: Attempt to extract from an empty FIFO!\n");
    return 0;
  }

  ST_message_t *myM = &myFifo.myMsgStruct[myFifo.StartPtr];
  strcpy(str, myM->msg); // Copy the message.

  uint16_t size = strlen(str);

  // Update FIFO pointers with wrap-around.
  myFifo.StartPtr = (myFifo.StartPtr + 1) % MQTT_QUEUE_SIZE;
  myFifo.noElements--;

  return size;
}

uint16_t peekFromFifo(char *str) {
  if (myFifo.noElements == 0) {
    printk("Error: Attempt to peek from an empty FIFO!\n");
    return 0;
  }

  ST_message_t *myM = &myFifo.myMsgStruct[myFifo.EndPtr - 1];
  strcpy(str, myM->msg); // Copy the message for peeking.

  return strlen(str);
}

int8_t overwriteLastMessage(ST_message_t *msg) {
  if (myFifo.noElements == 0) {
    printk("Error: Attempt to overwrite an empty FIFO!\n");
    return -1;
  }

  // Overwrite the message at the start pointer.
  memcpy(&myFifo.myMsgStruct[myFifo.EndPtr - 1], msg, sizeof(ST_message_t));

  return 0; // Successfully overwritten.
}

uint16_t fifoPull(char *str) {
  str[0] = '\0'; // Initialize with an empty string.
  uint16_t size = 0;

  // Check if data is available in FIFO.
  if (myFifo.noElements > 0) {
    size = extractFromFifo(str);
    return size;
  }

  // If FIFO is empty, attempt to import data from flash.
  uint8_t index;
  getFifoIndex(&index);

  importFifoFromFlash();

  // Recheck FIFO status after import.
  if (myFifo.noElements > 0) {
    size = extractFromFifo(str);
  } else {
    printk("Warning: No elements found in FIFO after flash import.\n");
    return 0;
  }

  return size;
}

extern unsigned long clockUnix;
void push_celltower_msg(char *msg) {
  ST_message_t cell_msg;
  cell_msg.idType = Id_Type_CyTrack;
  cell_msg.msgType = Msg_Type_LBS;
  strcpy(cell_msg.msg, msg);
  fifoPush(&cell_msg);
}

void push_lbs_msg(char *msg) {
  ST_message_t lbs;
  lbs.idType = Id_Type_CyTrack;
  lbs.msgType = Msg_Type_LBS;
  // strcpy(lbs.msg, msg);
  // fifoPush(&lbs);

  bool peek = peekFromFifo(lbs.msg);
  printk("lbs str lrngth = %d\r\n", strlen(lbs.msg));
  if (peek && strlen(lbs.msg) < 200) {
    char lbsField[100];
    strcpy(lbsField, msg);
    trimJsonBraces(lbsField);
    removeFirstField(lbsField);
    add_fields_to_json(lbs.msg, lbsField);
    lbsField[0] = '\0';
    return_power_status(lbsField, sizeof(lbsField));
    add_fields_to_json(lbs.msg, lbsField);

    overwriteLastMessage(&lbs);
  } else {
    lbs.msg[0] = '\0';
    strcpy(lbs.msg, msg);
    fifoPush(&lbs);
  }
}