"""Run with pvpython; requires compatible TTK plugin. See notebook section 6.
API reference: https://topology-tool-kit.github.io/examples/morsePersistence/
"""
from pathlib import Path
import argparse
import os
from paraview import simple as pvs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    plugin = os.environ.get("TTK_PLUGIN_PATH")
    if plugin:
        pvs.LoadPlugin(plugin, remote=False)
    if not hasattr(pvs, "TTKPersistenceDiagram"):
        raise RuntimeError("TTK plugin not loaded. Set TTK_PLUGIN_PATH to the compatible plugin library.")
    if not args.input.is_file():
        raise FileNotFoundError(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source = pvs.XMLImageDataReader(FileName=[str(args.input.resolve())])
    source.UpdatePipeline()
    diagram = pvs.TTKPersistenceDiagram(Input=source)
    diagram.ScalarField = ["POINTS", "height"]
    diagram.UpdatePipeline()
    morse = pvs.TTKMorseSmaleComplex(Input=source)
    morse.ScalarField = ["POINTS", "height"]
    morse.UpdatePipeline()
    pvs.SaveData(str(args.output_dir / "diagram.vtu"), proxy=diagram)
    pvs.SaveData(str(args.output_dir / "critical_points.vtp"), proxy=pvs.OutputPort(morse, 0))
    pvs.SaveData(str(args.output_dir / "separatrices.vtp"), proxy=pvs.OutputPort(morse, 1))
    # Morse-Smale segmentation preserves this input's vtkImageData geometry.
    pvs.SaveData(str(args.output_dir / "segmentation.vti"), proxy=pvs.OutputPort(morse, 3))
    print("TTK results saved to", args.output_dir.resolve())


if __name__ == "__main__":
    main()
