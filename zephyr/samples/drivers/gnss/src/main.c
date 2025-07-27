/*
 * Copyright (c) 2023 Trackunit Corporation
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gnss.h>
#include <zephyr/logging/log.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>

#define GNSS_MODEM DEVICE_DT_GET(DT_ALIAS(gnss))

LOG_MODULE_REGISTER(gnss_sample, CONFIG_GNSS_LOG_LEVEL);

static void gnss_data_cb(const struct device *dev, const struct gnss_data *data)
{
	if (data->info.fix_status != GNSS_FIX_STATUS_NO_FIX) {
		printf("Got a fix!\n");
	}
}
GNSS_DATA_CALLBACK_DEFINE(GNSS_MODEM, gnss_data_cb);

#if CONFIG_GNSS_SATELLITES
static void gnss_satellites_cb(const struct device *dev, const struct gnss_satellite *satellites,
			       uint16_t size)
{
	unsigned int tracked_count = 0;

	for (unsigned int i = 0; i != size; ++i) {
		tracked_count += satellites[i].is_tracked;
	}
	printf("%u satellite%s reported (of which %u tracked)!\n",
		size, size > 1 ? "s" : "", tracked_count);
}
#endif
GNSS_SATELLITES_CALLBACK_DEFINE(GNSS_MODEM, gnss_satellites_cb);



const struct device *gpio_device;
const struct device *gpio1;

void GPIO_INIT() {
  gpio_device = DEVICE_DT_GET(DT_ALIAS(gpio0));
  gpio1 = DEVICE_DT_GET(DT_ALIAS(gpio1));
  // gpio_pin_configure(gpio_device, PIN_MuxCTRL1, GPIO_OUTPUT);
  // gpio_pin_configure(gpio_device, PIN_MuxCTRL2, GPIO_OUTPUT);
  // gpio_pin_configure(gpio_device, PIN_BATTERY, GPIO_OUTPUT | GPIO_INPUT);
  // gpio_pin_configure(gpio_device, PIN_3V3_EX_EN, GPIO_OUTPUT | GPIO_INPUT);
  // gpio_pin_configure(gpio_device, PIN_SCL, GPIO_OUTPUT);
  // gpio_pin_configure(gpio_device, PIN_SDA, GPIO_OUTPUT);

  // gpio_pin_configure(gpio_device, PIN_nRF_PWRKEY, GPIO_OUTPUT);
  // gpio_pin_configure(gpio_device, PIN_5V_EN, GPIO_OUTPUT);
  // gpio_pin_configure(gpio_device, PIN_M_EN, GPIO_OUTPUT);
  // gpio_pin_configure(gpio_device, PIN_PWM, GPIO_OUTPUT);
  // gpio_pin_configure(gpio_device, PIN_DIR, GPIO_OUTPUT);
  // gpio_pin_configure(gpio_device, PIN_SAT_RESET, GPIO_OUTPUT);
  // gpio_pin_configure(gpio_device, PIN_SAT_PWR_ON, GPIO_OUTPUT);
  // gpio_pin_configure(gpio_device, PIN_LG, GPIO_OUTPUT);
  // gpio_pin_configure(gpio_device, PIN_LR, GPIO_OUTPUT);
  // gpio_pin_configure(gpio_device, PIN_LB, GPIO_OUTPUT);
  // gpio_pin_configure(gpio_device, PIN_ChargeFeedback, GPIO_INPUT);
  // gpio_pin_configure(gpio_device, PIN_Motor_input2_Connector_B, GPIO_OUTPUT);
  // gpio_pin_set(gpio_device, PIN_Motor_input2_Connector_B, 0);

  // gpio_pin_configure(gpio_device, PIN_Motor_input1_Switch_Feedback,
  //                    GPIO_INPUT | GPIO_OUTPUT | GPIO_ACTIVE_HIGH);
  // gpio_pin_set(gpio_device, PIN_Motor_input1_Switch_Feedback, 1);
  // //
  // gpio_pin_interrupt_configure(gpio_device,PIN_Motor_input1_Switch_Feedback,GPIO_INT_EDGE_RISING);

  // gpio_pin_configure(gpio_device, PIN_Motor_Output_1_Connector_A,
  //                    GPIO_INPUT | GPIO_ACTIVE_HIGH | GPIO_PULL_UP);
  // gpio_pin_interrupt_configure(gpio_device, PIN_Motor_Output_1_Connector_A,
  //                              GPIO_INT_EDGE_RISING);

  // gpio_pin_set(gpio_device, PIN_MuxCTRL1, 0);
  // gpio_pin_set(gpio_device, PIN_MuxCTRL2, 0);
  // gpio_pin_set(gpio_device, PIN_5V_EN, 0);
  // gpio_pin_set(gpio_device, PIN_DIR, 0);
  // gpio_pin_set(gpio_device, PIN_M_EN, 0);
  // gpio_pin_set(gpio_device, PIN_PWM, 0);
  // gpio_pin_set(gpio_device, PIN_SAT_PWR_ON, 0);
  // gpio_pin_set(gpio_device, PIN_SAT_RESET, 0);
  // gpio_pin_set(gpio_device, PIN_LR, 0);
  // gpio_pin_set(gpio_device, PIN_LB, 0);
  // gpio_pin_set(gpio_device, PIN_LG, 0);
  // gpio_pin_set(gpio_device, PIN_BATTERY, 0); // thuraya powerswitch
  // gpio_pin_set(gpio_device, PIN_3V3_EX_EN,
  //              1); // 3v3 powerswitch (microbus & flash memory)

  gpio_pin_configure(gpio1, 1, GPIO_OUTPUT);
  gpio_pin_set(gpio1, 0, 1);
//   k_msleep(300);
  // gpio_pin_configure(gpio_device, 8, GPIO_OUTPUT);
  // gpio_pin_set(gpio_device, 8, 1);
}


int main(void)
{
  	GPIO_INIT();

	// int err = gnss_set_fix_rate(GNSS_MODEM, 30 * 1000);
  // printk("\n\nfix rate %d\r\n\r\n\n\n\n\n",err);

	return 0;
}
