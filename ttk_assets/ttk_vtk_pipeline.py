"""Run the two TTK filters directly through VTK, without the ParaView plugin.

The macOS TTK package's top-level Python import eagerly loads optional filters.
Loading only the two extension modules used here avoids unrelated optional
dependencies, such as the Graphviz version needed by PlanarGraphLayout.
"""

import argparse
import importlib
import os
from pathlib import Path
import sys
import types

from vtkmodules.vtkIOXML import (
    vtkXMLImageDataReader,
    vtkXMLImageDataWriter,
    vtkXMLPolyDataWriter,
    vtkXMLUnstructuredGridWriter,
)


def load_filter_modules():
    module_dir = Path(os.environ["TTK_MODULE_DIR"])
    if not module_dir.is_dir():
        raise FileNotFoundError(f"TTK_MODULE_DIR does not exist: {module_dir}")
    package = types.ModuleType("topologytoolkit")
    package.__path__ = [str(module_dir)]
    sys.modules["topologytoolkit"] = package
    diagram_class = importlib.import_module(
        "topologytoolkit.ttkPersistenceDiagram"
    ).ttkPersistenceDiagram
    morse_class = importlib.import_module(
        "topologytoolkit.ttkMorseSmaleComplex"
    ).ttkMorseSmaleComplex
    return diagram_class, morse_class


def write_data(writer_class, data, path):
    writer = writer_class()
    writer.SetFileName(str(path))
    writer.SetInputData(data)
    if writer.Write() != 1:
        raise RuntimeError(f"Could not write {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(args.input)

    diagram_class, morse_class = load_filter_modules()
    reader = vtkXMLImageDataReader()
    reader.SetFileName(str(args.input.resolve()))
    reader.Update()
    if reader.GetOutput().GetPointData().GetArray("height") is None:
        raise ValueError("Input must contain a point scalar named 'height'")

    diagram = diagram_class()
    diagram.SetInputConnection(reader.GetOutputPort())
    diagram.SetInputArrayToProcess(0, 0, 0, 0, "height")
    diagram.Update()

    morse = morse_class()
    morse.SetInputConnection(reader.GetOutputPort())
    morse.SetInputArrayToProcess(0, 0, 0, 0, "height")
    morse.Update()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_data(vtkXMLUnstructuredGridWriter, diagram.GetOutputDataObject(0),
               args.output_dir / "diagram.vtu")
    write_data(vtkXMLPolyDataWriter, morse.GetOutputDataObject(0),
               args.output_dir / "critical_points.vtp")
    write_data(vtkXMLPolyDataWriter, morse.GetOutputDataObject(1),
               args.output_dir / "separatrices.vtp")
    write_data(vtkXMLImageDataWriter, morse.GetOutputDataObject(3),
               args.output_dir / "segmentation.vti")
    print(f"TTK results saved to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
