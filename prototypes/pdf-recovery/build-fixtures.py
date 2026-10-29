#!/usr/bin/python3
"""Build native fixtures beside the distribution shell, using its installed PDF library."""
from pathlib import Path
import re
import subprocess
import sys

source, inputs, build = map(Path, sys.argv[1:])
libraries = [p for p in Path("/usr/lib64").glob("libOkular6Core.so.*") if re.fullmatch(r"libOkular6Core\.so\.\d+", p.name)]
assert len(libraries) == 1, libraries
for name in ("capture", "departure", "retry"):
    (source / "shell" / (name + "-test.cpp")).write_bytes((inputs / (name + "-test.cpp")).read_bytes())
cmake = source / "shell/CMakeLists.txt"
assert "add_executable(monet_pdf_" not in cmake.read_text(), "Fixture targets already configured"
cmake.write_text(cmake.read_text() + """
set(monet_pdf_SRCS ${okular_SRCS})
list(REMOVE_ITEM monet_pdf_SRCS main.cpp)
foreach(test capture departure retry)
 add_executable(monet_pdf_${test} ${test}-test.cpp ${monet_pdf_SRCS})
 target_link_libraries(monet_pdf_${test} PRIVATE Qt6::Test Qt6::Xml Qt6::PrintSupport Qt6::GuiPrivate PkgConfig::MonetWayland KF6::I18n KF6::Parts KF6::WindowSystem KF6::Crash KF6::IconThemes KF6::KIOGui Qt6::DBus """ + str(libraries[0]) + """ )
endforeach()
""")
subprocess.run(["cmake", "-S", str(source), "-B", str(build)], check=True)
subprocess.run(["cmake", "--build", str(build), "--target", "okular", "monet_pdf_capture", "monet_pdf_departure", "monet_pdf_retry", "--parallel", "2"], check=True)
