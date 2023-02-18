from hat import aio
from hat.drivers import iec104
from hat.drivers import tcp
import asyncio
import pandapower.networks
import random
import sys


def main():
    aio.init_asyncio()
    aio.run_asyncio(async_main())


async def async_main():
    connections = set()

    def connection_cb(connection):
        connections.add(connection)
        connection.async_group.spawn(
            aio.call_on_cancel, lambda: connections.remove(connection)
        )

    server = await iec104.listen(
        connection_cb, tcp.Address("127.0.0.1", 20001)
    )
    try:
        while True:
            await asyncio.sleep(10)
            if not connections:
                continue

            net = pandapower.networks.case14()
            for load_id in range(len(net.load)):
                load = net.load.loc[load_id]
                net.load.loc[load_id, "p_mw"] = _randomize(load.p_mw)
                net.load.loc[load_id, "q_mvar"] = _randomize(
                    max(load.q_mvar, 0.1)
                )
            for gen_id in range(len(net.gen)):
                gen = net.gen.loc[gen_id]
                net.gen.loc[gen_id, "p_mw"] = _randomize(gen.p_mw)
                net.gen.loc[gen_id, "vm_pu"] = _randomize(gen.vm_pu)

            pandapower.runpp(net)

            data = []
            for bus in net.res_bus.iloc:
                data.append(_get_msg(int(bus.name), 0, bus.p_mw))
                data.append(_get_msg(int(bus.name), 1, bus.q_mvar))

            for connection in connections:
                connection.send(data)
    finally:
        server.close()
        for c in connections:
            c.close()


def _randomize(ref):
    return random.uniform(ref * 0.75, ref * 1.25)


def _get_msg(asdu, io, value):
    return iec104.DataMsg(
        asdu_address=asdu,
        io_address=io,
        data=iec104.FloatingData(
            value=iec104.FloatingValue(value),
            quality=iec104.MeasurementQuality(*[False] * 5),
        ),
        time=None,
        cause=iec104.DataResCause.SPONTANEOUS,
        is_test=False,
        originator_address=0,
    )


if __name__ == "__main__":
    sys.exit(main())
