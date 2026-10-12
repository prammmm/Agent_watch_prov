"""Unit tests for device selection and hardware diagnostics."""

import unittest
import torch
from agentwatch.utils.device import get_device, get_device_info


class TestDevice(unittest.TestCase):

    def test_get_device_cpu(self):
        dev = get_device(preferred_device="cpu")
        self.assertEqual(dev.type, "cpu")

    def test_get_device_cuda_detected(self):
        if torch.cuda.is_available():
            dev = get_device(require_gpu=True)
            self.assertEqual(dev.type, "cuda")
            self.assertEqual(dev.index, 0)
        else:
            with self.assertRaises(RuntimeError):
                get_device(require_gpu=True)

    def test_get_device_info(self):
        info = get_device_info()
        self.assertIn("pytorch_version", info)
        self.assertIn("cuda_available", info)
        if torch.cuda.is_available():
            self.assertTrue(info["cuda_available"])
            self.assertIsNotNone(info["device_name"])
            self.assertGreater(info["total_memory_bytes"], 0)
            self.assertIn("RTX 3060", info["device_name"])

    def test_tensor_cuda_execution_if_available(self):
        if torch.cuda.is_available():
            dev = get_device(require_gpu=True)
            x = torch.ones((10, 10), device=dev)
            y = torch.ones((10, 10), device=dev)
            z = x + y
            self.assertEqual(z.device.type, "cuda")
            self.assertEqual(z[0, 0].item(), 2.0)


if __name__ == "__main__":
    unittest.main()
