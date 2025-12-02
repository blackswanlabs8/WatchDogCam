import platform
import subprocess


def ping_host(ip: str, timeout_seconds: int = 1) -> bool:
    system = platform.system().lower()
    if system == "windows":
        command = ["ping", "-n", "1", "-w", str(timeout_seconds * 1000), ip]
    else:
        command = ["ping", "-c", "1", "-W", str(timeout_seconds), ip]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds + 1,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False
