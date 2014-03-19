# Description:
#   Build rules for vfsStream (stream wrapper for a virtual file system).

package(default_visibility = ["//visibility:public"])

licenses(["notice"])  # BSD

exports_files(["LICENSE"])

filegroup(
    name = "vfsstream_files",
    srcs = glob(
        ["vendor/**"],
        exclude = [
            "composer.json",
        ],
    ),
)

vfsstream_entries = [
    FilesetEntry(
        files = [":vfsstream_files"],
        strip_prefix = "",
    ),
]

Fileset(
    name = "vfsstream",
    out = "vfsstream",
    entries = vfsstream_entries,
)
