import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import automation, pins
from esphome.components import uart
from esphome.const import (
    CONF_ID,
    CONF_FLOW_CONTROL_PIN,
    CONF_SENSOR_DATAPOINT,
    CONF_TRIGGER_ID,
)
from esphome.cpp_helpers import gpio_pin_expression

DEPENDENCIES = ["uart"]

CONF_SRC_ADDRESS = "src_address"
CONF_DST_ADDRESS = "dst_address"
CONF_ON_DATAPOINT_UPDATE = "on_datapoint_update"
CONF_DATAPOINT_TYPE = "datapoint_type"
CONF_REQUEST_MOD = "request_mod"
CONF_REQUEST_ONCE = "request_once"
CONF_REQUEST_INTERVAL = "request_mod_update_intervals"

econet_ns = cg.esphome_ns.namespace("econet")
Econet = econet_ns.class_("Econet", cg.Component, uart.UARTDevice)
EconetClient = econet_ns.class_("EconetClient")

DPTYPE_RAW = "raw"

DATAPOINT_TYPES = {
    DPTYPE_RAW: cg.std_vector.template(cg.uint8),
}

DATAPOINT_TRIGGERS = {
    DPTYPE_RAW: econet_ns.class_(
        "EconetRawDatapointUpdateTrigger",
        automation.Trigger.template(DATAPOINT_TYPES[DPTYPE_RAW]),
    ),
}


def assign_declare_id(value):
    value = value.copy()
    value[CONF_TRIGGER_ID] = cv.declare_id(
        DATAPOINT_TRIGGERS[value[CONF_DATAPOINT_TYPE]]
    )(value[CONF_TRIGGER_ID].id)
    return value


def valid_request_mod(value):
    return cv.int_range(min=0, max=7)(value)


def request_mod(value):
    if isinstance(value, str) and value.lower() == "none":
        return -1
    return valid_request_mod(value)


def request_mod_interval_validator(value):
    cv.check_not_templatable(value)
    options_map_schema = cv.Schema(
        {valid_request_mod: cv.positive_time_period_milliseconds}
    )
    value = options_map_schema(value)
    all_values = list(value.keys())
    unique_values = set(value.keys())
    if len(all_values) != len(unique_values):
        raise cv.Invalid("Mapping values must be unique.")
    return value


CONFIG_SCHEMA = (
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(Econet),
            cv.Required(CONF_SRC_ADDRESS): cv.uint32_t,
            cv.Optional(CONF_DST_ADDRESS, default="0"): cv.uint32_t,
            cv.Optional(CONF_ON_DATAPOINT_UPDATE): automation.validate_automation(
                {
                    cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(
                        DATAPOINT_TRIGGERS[DPTYPE_RAW]
                    ),
                    cv.Required(CONF_SENSOR_DATAPOINT): cv.string,
                    cv.Optional(CONF_REQUEST_MOD, default="none"): request_mod,
                    cv.Optional(CONF_DATAPOINT_TYPE, default=DPTYPE_RAW): cv.one_of(
                        *DATAPOINT_TRIGGERS, lower=True
                    ),
                },
                extra_validators=assign_declare_id,
            ),
            cv.Optional(CONF_FLOW_CONTROL_PIN): pins.gpio_output_pin_schema,
            cv.Optional(CONF_REQUEST_INTERVAL): request_mod_interval_validator,
        }
    )
    .extend(cv.polling_component_schema("30s"))
    .extend(uart.UART_DEVICE_SCHEMA)
)

CONF_ECONET_ID = "econet_id"
ECONET_CLIENT_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_ECONET_ID): cv.use_id(Econet),
        cv.Optional(CONF_REQUEST_MOD, default=0): request_mod,
        cv.Optional(CONF_REQUEST_ONCE, default=False): cv.boolean,
    }
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await uart.register_uart_device(var, config)
    cg.add(var.set_src_address(config[CONF_SRC_ADDRESS]))
    cg.add(var.set_dst_address(config[CONF_DST_ADDRESS]))
    if CONF_REQUEST_INTERVAL in config:
        request_mod_interval_map = config[CONF_REQUEST_INTERVAL]
        cg.add(
            var.set_mod_req_updates_(
                list(request_mod_interval_map.keys()),
                list(request_mod_interval_map.values()),
            )
        )
    if CONF_FLOW_CONTROL_PIN in config:
        pin = await gpio_pin_expression(config[CONF_FLOW_CONTROL_PIN])
        cg.add(var.set_flow_control_pin(pin))
    for conf in config.get(CONF_ON_DATAPOINT_UPDATE, []):
        trigger = cg.new_Pvariable(
            conf[CONF_TRIGGER_ID],
            var,
            conf[CONF_SENSOR_DATAPOINT],
            conf[CONF_REQUEST_MOD],
        )
        await automation.build_automation(
            trigger, [(DATAPOINT_TYPES[conf[CONF_DATAPOINT_TYPE]], "x")], conf
        )
