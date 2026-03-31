#!/usr/bin/env python3
"""
Recompute constants in boxel_env.py for DEFAULT_DEBUG_VIS_*.

The ExampleBrowser camera uses yaw/pitch/distance around a target; the
semantic camera uses eye/target/up.  This script grid-searches
computeViewMatrixFromYawPitchRoll against computeViewMatrix for the default
eye and target.  Run after changing default camera_position / camera_target.

  source wsl_env/bin/activate && python3 tools/calibrate_debug_camera.py
"""
import numpy as np
import pybullet as p

EYE = np.array([0.5, -0.8, 0.7])
TARGET = np.array([0.5, 0.0, 0.5])
UP = np.array([0.0, 0.0, 1.0])


def main() -> None:
    cid = p.connect(p.DIRECT)
    want = p.computeViewMatrix(
        cameraEyePosition=EYE.tolist(),
        cameraTargetPosition=TARGET.tolist(),
        cameraUpVector=UP.tolist(),
    )
    dist = float(np.linalg.norm(EYE - TARGET))
    best = (1e99, 0.0, 0.0)
    for yaw in np.arange(-2.0, 2.01, 0.02):
        for pitch in np.arange(-16.0, -12.0, 0.02):
            vm = p.computeViewMatrixFromYawPitchRoll(
                cameraTargetPosition=TARGET.tolist(),
                distance=dist,
                yaw=float(yaw),
                pitch=float(pitch),
                roll=0,
                upAxisIndex=2,
            )
            err = sum(abs(a - b) for a, b in zip(want, vm))
            if err < best[0]:
                best = (err, yaw, pitch)
    p.disconnect()
    err, yaw, pitch = best
    print(f"dist = {repr(dist)}")
    print(f"yaw  = {repr(float(yaw))}")
    print(f"pitch = {repr(float(pitch))}")
    print(f"target = {TARGET.tolist()}")
    print(f"view matrix L1 error vs semantic: {err}")


if __name__ == "__main__":
    main()
