"""Phase 3-B ITEM 5: the ONE fixed arm config from which sensing is legal, and
extraction of the wrist camera's world pose at that config.

Our model is a FIXED camera; TAMPURA's is eye-in-hand. We reconcile them by
allowing SENSE only from a single constant arm config whose wrist camera images
the table. Candidate (and used): their DEFAULT_ARM_POS (home) — env.initialize
images from exactly this config to build the initial belief (env.py:853-856), so
it provably views table+cups; the die is hidden under the cup.

The wrist camera frame == optical frame (robot.py:9-10), so the camera EYE we
feed our oracle/shadow is robot.camera.get_pose()[0] at this config. Our
perception uses only the eye (camera_position); the look target matters solely
for image rendering / debug view.
"""
import os
import numpy as np

from tampura_environments.panda_utils import pb_utils as pbu
from tampura_environments.panda_utils.robot import (
    ARM_GROUP,
    DEFAULT_ARM_POS,
    HEIGHT,
    WIDTH,
)

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The single arm configuration sensing is allowed from (GOAL 3: "sense at home").
SENSE_ARM_CONF = list(DEFAULT_ARM_POS)


def set_sense_config(world):
    """Teleport the arm to SENSE_ARM_CONF on `world` (the state world)."""
    world.robot.set_group_positions(ARM_GROUP, SENSE_ARM_CONF, client=world.client)


def is_at_sense_config(world, atol=1e-4):
    """True iff the arm is at SENSE_ARM_CONF (the at-home gate reused by ITEM 13)."""
    joints = world.robot.get_group_joints(ARM_GROUP, client=world.client)
    cur = pbu.get_joint_positions(world.robot.body, joints, client=world.client)
    return bool(np.allclose(cur, SENSE_ARM_CONF, atol=atol))


def sense_camera_pose(world):
    """(eye_xyz, quat_xyzw) of the wrist camera frame at the CURRENT arm config."""
    eye, quat = world.robot.camera.get_pose(client=world.client)
    return np.array(eye, dtype=float), np.array(quat, dtype=float)


def sense_camera_position(world):
    """The camera EYE our oracle/shadow consume as camera_position."""
    return sense_camera_pose(world)[0]


def capture_sense_image(world, save_path):
    """Set the sense config, render the wrist camera, save RGB PNG (absolute path)."""
    from PIL import Image

    set_sense_config(world)
    ci = world.robot.get_image(client=world.client)
    rgb = getattr(ci, "rgbPixels", None)
    if rgb is None:
        rgb = ci[0]
    rgb = np.asarray(rgb, dtype=np.uint8)
    if rgb.ndim == 1:
        rgb = rgb.reshape(HEIGHT, WIDTH, 4)
    rgb = rgb[:, :, :3]
    abspath = os.path.abspath(save_path)
    os.makedirs(os.path.dirname(abspath), exist_ok=True)
    Image.fromarray(rgb).save(abspath)
    return abspath


def _main():
    import argparse
    import logging
    import random
    import time

    from tampura.config import config as tconfig
    import tampura_environments  # noqa: F401 — registers the find_dice env

    p = argparse.ArgumentParser(description="ITEM 5: sense config + wrist camera pose")
    p.add_argument("--config", default="./env_configs/find_dice.yml")
    p.add_argument("--global-seed", type=int)
    p.add_argument("--vis", type=int, default=1)
    p.add_argument(
        "--save-dir",
        default=os.path.join(os.getcwd(), "runs", "boxel_sense_{}".format(time.time())),
    )
    p.add_argument(
        "--out",
        default=os.path.join(_REPO, "tampura_bridge", "captures", "item5_sense_view_home.png"),
    )
    args = p.parse_args()
    arg_dict = {k: v for k, v in vars(args).items() if v is not None and k != "out"}

    config = tconfig.load_config(config_file=arg_dict["config"], arg_dict=arg_dict)
    random.seed(config["global_seed"])
    np.random.seed(config["global_seed"])
    tconfig.setup_logger(config["save_dir"], log_level=logging.INFO)

    env = tconfig.get_env(config["task"])(config=config)
    b0, store = env.initialize()
    world = env.world

    set_sense_config(world)
    eye, quat = sense_camera_pose(world)
    logging.info("[ITEM5] SENSE_ARM_CONF = %s", SENSE_ARM_CONF)
    logging.info("[ITEM5] camera_position (eye) = %s", eye.tolist())
    logging.info("[ITEM5] camera quat (xyzw)    = %s", quat.tolist())
    saved = capture_sense_image(world, args.out)
    logging.info("[ITEM5] at sense config? %s", is_at_sense_config(world))
    logging.info("[ITEM5] wrist sense image saved -> %s", saved)


if __name__ == "__main__":
    _main()
