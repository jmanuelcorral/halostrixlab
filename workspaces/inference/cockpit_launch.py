from pathlib import Path


def halogen_device_groups(engine, arguments):
    result = list(arguments)
    if engine != "docker":
        return result
    devices = {"render": Path("/dev/dri/renderD128"), "video": Path("/dev/dri/card0")}
    for index, argument in enumerate(result):
        if index and result[index - 1] == "--group-add" and argument in devices:
            result[index] = str(devices[argument].stat().st_gid)
        elif argument.startswith("--group-add="):
            name = argument.split("=", 1)[1]
            if name in devices:
                result[index] = "--group-add=" + str(devices[name].stat().st_gid)
    return result


def main():
    from ai_toolbox_cockpit.backends.halogen import runner

    original = runner.build_server_cmd

    def build_server_cmd(**kwargs):
        kwargs["engine_args"] = halogen_device_groups(kwargs["engine"], kwargs["engine_args"])
        return original(**kwargs)

    runner.build_server_cmd = build_server_cmd
    from ai_toolbox_cockpit.backends.halogen import server

    server.build_server_cmd = build_server_cmd
    from ai_toolbox_cockpit.main import cli_main

    cli_main()


if __name__ == "__main__":
    main()
