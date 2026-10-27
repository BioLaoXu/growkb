#!/usr/bin/env python3
"""kb_tsv_stats —— 计算 TSV 数值列的摘要统计（CLI 薄壳：业务逻辑可上移至 code/python/）

用法：
    kb_tsv_stats.py --input <tsv> [--sep '\t'] [--columns c1,c2]
输出：列名 -> count/mean/min/max，TSV 打印到 stdout。
"""
import argparse
import sys


def tsv_stats(path: str, sep: str = '\t', columns=None) -> dict:
    """计算 TSV 数值列的 count/mean/min/max。

    Args:
        path: TSV 文件路径（首行为表头）。
        sep: 分隔符，默认制表符。
        columns: 要统计的列名列表；缺省为全部可解析为数值的列。

    Returns:
        dict: 列名 -> {'count': n, 'mean': x, 'min': x, 'max': x}。

    Raises:
        SystemExit: 文件不存在或没有可统计的数值列。
    """
    import os
    if not os.path.isfile(path):
        sys.exit('[ERROR] 文件不存在：%s' % path)
    rows, header = [], []
    with open(path, encoding='utf-8') as fh:
        header = fh.readline().rstrip('\n').split(sep)
        for line in fh:
            if line.strip():
                rows.append(line.rstrip('\n').split(sep))
    target = columns if columns else header
    out = {}
    for col in target:
        if col not in header:
            continue
        idx = header.index(col)
        vals = []
        for r in rows:
            try:
                vals.append(float(r[idx]))
            except (ValueError, IndexError):
                pass
        if vals:
            out[col] = {'count': len(vals),
                        'mean': sum(vals) / len(vals),
                        'min': min(vals), 'max': max(vals)}
    if not out:
        sys.exit('[ERROR] 没有可统计的数值列')
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', required=True, help='输入 TSV 文件路径（必填）')
    parser.add_argument('--sep', default='\t', help='分隔符（默认制表符）')
    parser.add_argument('--columns', default=None, help='逗号分隔的列名；缺省自动识别数值列')
    args = parser.parse_args(argv)
    cols = args.columns.split(',') if args.columns else None
    stats = tsv_stats(args.input, args.sep, cols)
    print('column\tcount\tmean\tmin\tmax')
    for col, st in stats.items():
        print('%s\t%d\t%.4g\t%.4g\t%.4g' % (col, st['count'], st['mean'], st['min'], st['max']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
