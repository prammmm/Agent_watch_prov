"""AgentWatch device management utility.

Provides standardized, verifiable GPU device selection for PyTorch workloads
on the target NVIDIA GeForce RTX 3060.
"""

from typing import Optional
import torch


def get_device(require_gpu: bool = False, preferred_device: Optional[str] = None) -> torch.device:
    """Select and verify the compute device for PyTorch workloads.

    Args:
        require_gpu: If True, raises RuntimeError if CUDA is unavailable.
        preferred_device: Explicit device string override (e.g. 'cuda:0', 'cpu').

    Returns:
        torch.device: The resolved device.

    Raises:
        RuntimeError: If require_gpu is True and CUDA is not available.
    """
    if preferred_device is not None:
        device = torch.device(preferred_device)
        if device.type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(
                f"Requested CUDA device '{preferred_device}', but CUDA is not available."
            )
        return device

    if torch.cuda.is_available():
        return torch.device("cuda:0")

    if require_gpu:
        raise RuntimeError(
            "CUDA is unavailable. Check the NVIDIA driver and the installed PyTorch build."
        )

    return torch.device("cpu")


def get_device_info() -> dict:
    """Return verified metadata about compute hardware and PyTorch CUDA state."""
    cuda_available = torch.cuda.is_available()
    info = {
        "pytorch_version": torch.__version__,
        "cuda_available": cuda_available,
        "device_count": torch.cuda.device_count() if cuda_available else 0,
        "device_name": torch.cuda.get_device_name(0) if cuda_available else None,
        "compute_capability": torch.cuda.get_device_capability(0) if cuda_available else None,
        "total_memory_bytes": torch.cuda.get_device_properties(0).total_memory if cuda_available else None,
    }
    return info


if __name__ == "__main__":
    dev = get_device(require_gpu=True)
    info = get_device_info()
    print(f"Device: {dev}")
    print(f"Device Name: {info['device_name']}")
    print(f"CUDA Available: {info['cuda_available']}")
    print(f"PyTorch Version: {info['pytorch_version']}")
    print(f"Total VRAM (MB): {info['total_memory_bytes'] / (1024 ** 2):.1f}")
