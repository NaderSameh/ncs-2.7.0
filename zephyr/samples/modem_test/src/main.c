#include <zephyr/kernel.h>
#include <zephyr/drivers/uart.h>
#include <string.h>
#include <zephyr/drivers/cellular.h>
#include <zephyr/modem/chat.h>
#include <zephyr/pm/device.h>
#include <string.h>
#include <inttypes.h>
#include <stdio.h>
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/logging/log.h>
#include <zephyr/kernel.h>
#include <zephyr/net/dns_resolve.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/socket.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/modem/chat.h>

#include <string.h>
#include <zephyr/device.h>
#include <zephyr/drivers/cellular.h>

#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/net/dns_resolve.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/socket.h>
#include <zephyr/pm/device.h>
#include <zephyr/pm/device_runtime.h>

#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/modem/chat.h>

#include <inttypes.h>
#include <stdio.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/pm/device.h>
#include <zephyr/sys/poweroff.h>
#include <zephyr/sys/util.h>

LOG_MODULE_REGISTER(main);


const struct device *modem = DEVICE_DT_GET(DT_ALIAS(modem));

#define UART_DEVICE_NODE DT_NODELABEL(uart2)
const struct device *uart1_dev = DEVICE_DT_GET(UART_DEVICE_NODE);

#define CMD_BUFFER_LEN 64

uint32_t raised_event;
const void *info;
size_t info_len;

char URL_sub[102] =
    "https://beyti.cypod.solutions:5000/device/configurations?IMEI=";
char ota_update_url[65] = "https://beyti.cypod.solutions:5000/remote/update/";
char URL_len[20];
uint16_t URL_len_len;
bool OTAupdate = false;
const struct device *gpio1;
const struct device *gpio_device;
struct device *flash_dev;
 unsigned long clockUnix;
char IMEI[20];
uint8_t simSelect = 0;
extern uint8_t simMode[11];

void parseConfig(char *config) {
    printk("Config: %s\n", config);
}

void select_sim(uint8_t mode) {
  printk("Selecting SIM %d\r\n", mode);

  if (mode == 1) {
    strcpy(simMode, "AT+QDSIM=1");
    LOG_INF("Physical SIM 1 %s\r\n", simMode);
  } else if (mode == 0) {
    strcpy(simMode, "AT+QDSIM=0");
    LOG_INF("Physical SIM 0 %s\r\n", simMode);
  }
}

int StartModem(void) {
    select_sim(simSelect);
    LOG_INF("Powering on modem\n");
    pm_device_action_run(modem, PM_DEVICE_ACTION_RESUME);
    int ret = net_if_down(net_if_get_default());
    if (ret < 0) {
      LOG_INF("Failed to bring down network interface\n");
    }

    LOG_INF("Waiting for L4 connected\n");

    ret = net_mgmt_event_wait_on_iface(net_if_get_default(),
                                        NET_EVENT_L4_CONNECTED, &raised_event,
                                        &info, &info_len, K_SECONDS(120));
    if (ret != 0) {
        LOG_INF("L4 was not connected in time\n");
        return -1;
    } else{
      LOG_ERR("HEREEEEEEE!!!!");
        printk("Raised event = %X\n", raised_event);
        // printk("Raised event = %X\n", raised_event);
        if (raised_event == 0xF1140003) {
            printk("Raised event = CONNECTED\n");
            return 0;
        } else if (raised_event == 0xF1140002) {
            printk("Raised event = DISCONNECTED\n");
        }
    }
}

extern int modem_cellular_clock(const struct device *dev);
extern int modem_cellular_get_lbs_location(const struct device *dev);


void ReportMessages(void) {
  // k_msgq_get(&my_msgq, &data, K_FOREVER);
  int ret = 0;
  while (1) {
    int ret = StartModem();
    if (ret != 0) {
        LOG_ERR("Failed to start modem, ret = %d", ret);
    }
    LOG_ERR("ENDEDDDDD????!");
    modem_cellular_clock(modem);
    modem_cellular_get_lbs_location(modem);
    k_msleep(100000);

  }
}
K_THREAD_STACK_DEFINE(thread_stack, 1024);
struct k_thread report_thread;
int main(void)
{

k_thread_create(&report_thread, thread_stack,
                K_THREAD_STACK_SIZEOF(thread_stack), ReportMessages, NULL,
                NULL, NULL, 4, 0, K_NO_WAIT);

    while (1) {
        k_sleep(K_MSEC(10));
        // uint8_t c;

        // if (uart_poll_in(uart1_dev, &c) == 0) {
        //     // Echo the input char back
        //     // uart_poll_out(uart1_dev, c);

        //     if (pos < CMD_BUFFER_LEN - 1) {
        //         buf[pos++] = c;

        //         // Check for \r\n (end of command)
        //         if (pos >= 2 && buf[pos - 2] == '\r' && buf[pos - 1] == '\n') {
        //             buf[pos] = '\0';  // Null-terminate string

        //             if (strcmp((char *)buf, "echo test\r\n") == 0) {
		// 				printk("Received command: %s", buf);
        //                 const char *reply = "OK\r\n";
        //                 for (int i = 0; reply[i]; i++) {
        //                     uart_poll_out(uart1_dev, reply[i]);
        //                 }
        //             } else {
        //                 const char *reply = "ERR\r\n";
        //                 for (int i = 0; reply[i]; i++) {
        //                     uart_poll_out(uart1_dev, reply[i]);
        //                 }
        //             }

        //             // Reset buffer after command processed
        //             pos = 0;
        //         }
        //     } else {
        //         // Buffer overflow, reset
        //         pos = 0;
        //     }
        // }


    }
    return 0;
}
