#include <zephyr/kernel.h>
#include <zephyr/drivers/uart.h>
#include <string.h>
#include <zephyr/drivers/gnss.h>
#include <zephyr/pm/device.h>
#include <string.h>
#include <inttypes.h>
#include <stdio.h>
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(main);


#define UART_DEVICE_NODE DT_NODELABEL(uart2)
const struct device *uart1_dev = DEVICE_DT_GET(UART_DEVICE_NODE);

#define CMD_BUFFER_LEN 64

#define GNSS_MODEM DEVICE_DT_GET(DT_ALIAS(gnss))

unsigned long clockUnix = 0;
int gnss_dump_nav_data2(char *str, uint16_t strsize,
                        const struct navigation_data *nav_data, uint8_t no_sat,
                        uint32_t accuracy) {
  int ret;
  const char *fmt = "{\"T\":%d,\"lat\": %s%lli.%09lli, \"lng\": %s%lli.%09lli, "
                    "\"bearing\": %u.%03u, \"kmph\": %u.%03u, \"alt\": "
                    "%s%i.%03i, "
                    "\"no_sat\":%u, \"hdop\":%u.%03u}";
  char *lat_sign = nav_data->latitude < 0 ? "-" : "";
  char *lon_sign = nav_data->longitude < 0 ? "-" : "";
  char *alt_sign = nav_data->altitude < 0 ? "-" : "";

  LOG_INF("Speed in mms = %d\r\n", nav_data->speed);
  double speed_kmph = nav_data->speed * 0.0036;
  LOG_INF("Speed in kmph = %f\r\n", speed_kmph);

  // Separate integer and fractional parts
  uint32_t int_part = (uint32_t)speed_kmph;
  uint32_t frac_part = (uint32_t)((speed_kmph - int_part) * 100); //

  ret = snprintk(str, strsize, fmt, clockUnix, lat_sign,
                 llabs(nav_data->latitude) / 1000000000,
                 llabs(nav_data->latitude) % 1000000000, lon_sign,
                 llabs(nav_data->longitude) / 1000000000,
                 llabs(nav_data->longitude) % 1000000000,
                 nav_data->bearing / 1000, nav_data->bearing % 1000, int_part,
                 frac_part, alt_sign, abs(nav_data->altitude) / 1000,
                 abs(nav_data->altitude) % 1000, no_sat, accuracy / 1000,
                 accuracy % 1000);

  return (strsize < ret) ? -ENOMEM : 0;
}


static void gnss_data_cb(const struct device *dev,
                         const struct gnss_data *data) {
	static uint8_t fixCounter = 0; // Counter for the number of fixes

	uint8_t sat_cnt = data->info.satellites_cnt;
	uint32_t hdop_acc = data->info.hdop;
	printk(
		"\r\n ********************** Got a fix! %d ***********************\r\n",
		fixCounter);
	char buf[300];
	gnss_dump_nav_data2(buf, sizeof(buf), &data->nav_data, sat_cnt, hdop_acc);
		// const char *reply = "ERR\r\n";
		for (int i = 0; buf[i]; i++) {
			uart_poll_out(uart1_dev, buf[i]);
		}
	
}
GNSS_DATA_CALLBACK_DEFINE(GNSS_MODEM, gnss_data_cb);

void main(void)
{
    if (!device_is_ready(uart1_dev)) {
        printk("UART1 not ready\n");
        return;
    }

    pm_device_action_run(GNSS_MODEM, PM_DEVICE_ACTION_RESUME);
	device_init(GNSS_MODEM);

    printk("UART command handler started 2222222\n");

    uint8_t buf[CMD_BUFFER_LEN];
    size_t pos = 0;

    while (1) {
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

        k_sleep(K_MSEC(10));
    }
}
