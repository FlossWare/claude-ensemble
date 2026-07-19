#!/usr/bin/env python3
"""pandas documentation scraper.

Covers:
  - pandas user guide (getting started, IO, indexing, reshaping, etc.)
  - pandas API reference (DataFrame, Series, Index, general functions)
  - pandas extensions and type utilities
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class PandasScraper(BaseScraper):
    """Scrape pandas documentation and API reference."""

    SOURCES = {
        "getting-started": {
            "pages": {
                "https://pandas.pydata.org/docs/": "pandas Documentation",
                "https://pandas.pydata.org/docs/getting_started/index.html": "Getting Started",
                "https://pandas.pydata.org/docs/getting_started/install.html": "Installation",
                "https://pandas.pydata.org/docs/getting_started/overview.html": "Package Overview",
                "https://pandas.pydata.org/docs/getting_started/intro_tutorials/index.html": "Intro Tutorials",
                "https://pandas.pydata.org/docs/getting_started/intro_tutorials/01_table_oriented.html": "What kind of data does pandas handle",
                "https://pandas.pydata.org/docs/getting_started/intro_tutorials/02_read_write.html": "Read and Write Data",
                "https://pandas.pydata.org/docs/getting_started/intro_tutorials/03_subset_data.html": "Select Subset of Data",
                "https://pandas.pydata.org/docs/getting_started/intro_tutorials/04_plotting.html": "Plotting",
                "https://pandas.pydata.org/docs/getting_started/intro_tutorials/05_add_columns.html": "Create New Columns",
                "https://pandas.pydata.org/docs/getting_started/intro_tutorials/06_calculate_statistics.html": "Calculate Statistics",
                "https://pandas.pydata.org/docs/getting_started/intro_tutorials/07_reshape_table_layout.html": "Reshape Table Layout",
                "https://pandas.pydata.org/docs/getting_started/intro_tutorials/08_combine_dataframes.html": "Combine DataFrames",
                "https://pandas.pydata.org/docs/getting_started/intro_tutorials/09_timeseries.html": "Time Series",
                "https://pandas.pydata.org/docs/getting_started/intro_tutorials/10_text_data.html": "Text Data",
                "https://pandas.pydata.org/docs/getting_started/comparison/index.html": "Comparison with Other Tools",
                "https://pandas.pydata.org/docs/getting_started/comparison/comparison_with_r.html": "Comparison with R",
                "https://pandas.pydata.org/docs/getting_started/comparison/comparison_with_sql.html": "Comparison with SQL",
                "https://pandas.pydata.org/docs/getting_started/comparison/comparison_with_spreadsheets.html": "Comparison with Spreadsheets",
                "https://pandas.pydata.org/docs/getting_started/comparison/comparison_with_sas.html": "Comparison with SAS",
                "https://pandas.pydata.org/docs/getting_started/comparison/comparison_with_stata.html": "Comparison with Stata",
            },
        },
        "io": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/io.html": "IO Tools",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html": "read_csv",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html": "to_csv",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html": "read_excel",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_excel.html": "to_excel",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_json.html": "read_json",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_json.html": "to_json",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_html.html": "read_html",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_html.html": "to_html",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_sql.html": "read_sql",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_sql.html": "to_sql",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_parquet.html": "read_parquet",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_parquet.html": "to_parquet",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_feather.html": "read_feather",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_hdf.html": "read_hdf",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_pickle.html": "read_pickle",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_pickle.html": "to_pickle",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_clipboard.html": "read_clipboard",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_fwf.html": "read_fwf",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_xml.html": "read_xml",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_orc.html": "read_orc",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_stata.html": "read_stata",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_sas.html": "read_sas",
                "https://pandas.pydata.org/docs/reference/api/pandas.read_spss.html": "read_spss",
            },
        },
        "indexing": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/indexing.html": "Indexing and Selecting Data",
                "https://pandas.pydata.org/docs/user_guide/advanced.html": "MultiIndex / Advanced Indexing",
                "https://pandas.pydata.org/docs/user_guide/boolean.html": "Boolean Indexing",
                "https://pandas.pydata.org/docs/user_guide/duplicates.html": "Duplicate Labels",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.loc.html": "DataFrame.loc",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.iloc.html": "DataFrame.iloc",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.at.html": "DataFrame.at",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.iat.html": "DataFrame.iat",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.xs.html": "DataFrame.xs",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.query.html": "DataFrame.query",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.where.html": "DataFrame.where",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.mask.html": "DataFrame.mask",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.set_index.html": "DataFrame.set_index",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.reset_index.html": "DataFrame.reset_index",
                "https://pandas.pydata.org/docs/reference/api/pandas.MultiIndex.html": "MultiIndex",
                "https://pandas.pydata.org/docs/reference/api/pandas.Index.html": "Index",
            },
        },
        "merge-join": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/merging.html": "Merge, Join, Concatenate",
                "https://pandas.pydata.org/docs/reference/api/pandas.merge.html": "pandas.merge",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html": "DataFrame.merge",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.join.html": "DataFrame.join",
                "https://pandas.pydata.org/docs/reference/api/pandas.concat.html": "pandas.concat",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.combine.html": "DataFrame.combine",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.combine_first.html": "DataFrame.combine_first",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.update.html": "DataFrame.update",
                "https://pandas.pydata.org/docs/reference/api/pandas.merge_ordered.html": "merge_ordered",
                "https://pandas.pydata.org/docs/reference/api/pandas.merge_asof.html": "merge_asof",
            },
        },
        "reshaping": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/reshaping.html": "Reshaping and Pivot Tables",
                "https://pandas.pydata.org/docs/reference/api/pandas.pivot_table.html": "pivot_table",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.pivot.html": "DataFrame.pivot",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.pivot_table.html": "DataFrame.pivot_table",
                "https://pandas.pydata.org/docs/reference/api/pandas.melt.html": "pandas.melt",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.melt.html": "DataFrame.melt",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.stack.html": "DataFrame.stack",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.unstack.html": "DataFrame.unstack",
                "https://pandas.pydata.org/docs/reference/api/pandas.crosstab.html": "pandas.crosstab",
                "https://pandas.pydata.org/docs/reference/api/pandas.get_dummies.html": "get_dummies",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.explode.html": "DataFrame.explode",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.transpose.html": "DataFrame.transpose",
            },
        },
        "text": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/text.html": "Working with Text Data",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.str.html": "Series.str accessor",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.str.contains.html": "str.contains",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.str.replace.html": "str.replace",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.str.split.html": "str.split",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.str.strip.html": "str.strip",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.str.lower.html": "str.lower",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.str.upper.html": "str.upper",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.str.cat.html": "str.cat",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.str.extract.html": "str.extract",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.str.findall.html": "str.findall",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.str.match.html": "str.match",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.str.len.html": "str.len",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.str.startswith.html": "str.startswith",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.str.endswith.html": "str.endswith",
            },
        },
        "categorical": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/categorical.html": "Categorical Data",
                "https://pandas.pydata.org/docs/reference/api/pandas.Categorical.html": "pandas.Categorical",
                "https://pandas.pydata.org/docs/reference/api/pandas.CategoricalDtype.html": "CategoricalDtype",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.cat.html": "Series.cat accessor",
                "https://pandas.pydata.org/docs/reference/api/pandas.CategoricalIndex.html": "CategoricalIndex",
            },
        },
        "missing-data": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/missing_data.html": "Working with Missing Data",
                "https://pandas.pydata.org/docs/reference/api/pandas.isna.html": "pandas.isna",
                "https://pandas.pydata.org/docs/reference/api/pandas.notna.html": "pandas.notna",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.isna.html": "DataFrame.isna",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.notna.html": "DataFrame.notna",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.fillna.html": "DataFrame.fillna",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.dropna.html": "DataFrame.dropna",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.interpolate.html": "DataFrame.interpolate",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.bfill.html": "DataFrame.bfill",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.ffill.html": "DataFrame.ffill",
                "https://pandas.pydata.org/docs/reference/api/pandas.NA.html": "pandas.NA",
                "https://pandas.pydata.org/docs/reference/api/pandas.NaT.html": "pandas.NaT",
            },
        },
        "visualization": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/visualization.html": "Chart Visualization",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.plot.html": "DataFrame.plot",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.plot.bar.html": "DataFrame.plot.bar",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.plot.barh.html": "DataFrame.plot.barh",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.plot.box.html": "DataFrame.plot.box",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.plot.hist.html": "DataFrame.plot.hist",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.plot.kde.html": "DataFrame.plot.kde",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.plot.line.html": "DataFrame.plot.line",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.plot.scatter.html": "DataFrame.plot.scatter",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.plot.pie.html": "DataFrame.plot.pie",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.plot.area.html": "DataFrame.plot.area",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.plot.hexbin.html": "DataFrame.plot.hexbin",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.hist.html": "DataFrame.hist",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.boxplot.html": "DataFrame.boxplot",
                "https://pandas.pydata.org/docs/reference/api/pandas.plotting.scatter_matrix.html": "scatter_matrix",
            },
        },
        "computation": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/computation.html": "Computational Tools",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.apply.html": "DataFrame.apply",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.applymap.html": "DataFrame.applymap",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.agg.html": "DataFrame.agg",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.transform.html": "DataFrame.transform",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.pipe.html": "DataFrame.pipe",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.corr.html": "DataFrame.corr",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.cov.html": "DataFrame.cov",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rank.html": "DataFrame.rank",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.pct_change.html": "DataFrame.pct_change",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.diff.html": "DataFrame.diff",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.eval.html": "DataFrame.eval",
            },
        },
        "groupby": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/groupby.html": "Group By: split-apply-combine",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.groupby.html": "DataFrame.groupby",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.GroupBy.html": "GroupBy",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.GroupBy.apply.html": "GroupBy.apply",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.GroupBy.agg.html": "GroupBy.agg",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.GroupBy.transform.html": "GroupBy.transform",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.GroupBy.filter.html": "GroupBy.filter",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.GroupBy.first.html": "GroupBy.first",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.GroupBy.last.html": "GroupBy.last",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.GroupBy.nth.html": "GroupBy.nth",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.GroupBy.sum.html": "GroupBy.sum",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.GroupBy.mean.html": "GroupBy.mean",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.GroupBy.count.html": "GroupBy.count",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.GroupBy.size.html": "GroupBy.size",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.GroupBy.describe.html": "GroupBy.describe",
                "https://pandas.pydata.org/docs/reference/api/pandas.NamedAgg.html": "NamedAgg",
            },
        },
        "windowing": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/window.html": "Windowing Operations",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html": "DataFrame.rolling",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.expanding.html": "DataFrame.expanding",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.ewm.html": "DataFrame.ewm",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.window.rolling.Rolling.html": "Rolling",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.window.expanding.Expanding.html": "Expanding",
                "https://pandas.pydata.org/docs/reference/api/pandas.core.window.ewm.ExponentialMovingWindow.html": "ExponentialMovingWindow",
            },
        },
        "time-series": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/timeseries.html": "Time Series / Date Functionality",
                "https://pandas.pydata.org/docs/reference/api/pandas.to_datetime.html": "to_datetime",
                "https://pandas.pydata.org/docs/reference/api/pandas.date_range.html": "date_range",
                "https://pandas.pydata.org/docs/reference/api/pandas.period_range.html": "period_range",
                "https://pandas.pydata.org/docs/reference/api/pandas.timedelta_range.html": "timedelta_range",
                "https://pandas.pydata.org/docs/reference/api/pandas.Timestamp.html": "Timestamp",
                "https://pandas.pydata.org/docs/reference/api/pandas.DatetimeIndex.html": "DatetimeIndex",
                "https://pandas.pydata.org/docs/reference/api/pandas.Period.html": "Period",
                "https://pandas.pydata.org/docs/reference/api/pandas.PeriodIndex.html": "PeriodIndex",
                "https://pandas.pydata.org/docs/reference/api/pandas.Timedelta.html": "Timedelta",
                "https://pandas.pydata.org/docs/reference/api/pandas.TimedeltaIndex.html": "TimedeltaIndex",
                "https://pandas.pydata.org/docs/reference/api/pandas.tseries.offsets.DateOffset.html": "DateOffset",
                "https://pandas.pydata.org/docs/reference/api/pandas.tseries.offsets.BusinessDay.html": "BusinessDay",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.resample.html": "DataFrame.resample",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.shift.html": "DataFrame.shift",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.asfreq.html": "DataFrame.asfreq",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.dt.html": "Series.dt accessor",
            },
        },
        "timedeltas": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/timedeltas.html": "Time Deltas",
                "https://pandas.pydata.org/docs/reference/api/pandas.to_timedelta.html": "to_timedelta",
            },
        },
        "options": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/options.html": "Options and Settings",
                "https://pandas.pydata.org/docs/reference/api/pandas.set_option.html": "set_option",
                "https://pandas.pydata.org/docs/reference/api/pandas.get_option.html": "get_option",
                "https://pandas.pydata.org/docs/reference/api/pandas.reset_option.html": "reset_option",
                "https://pandas.pydata.org/docs/reference/api/pandas.option_context.html": "option_context",
                "https://pandas.pydata.org/docs/reference/api/pandas.describe_option.html": "describe_option",
            },
        },
        "enhancingperf": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/enhancingperf.html": "Enhancing Performance",
                "https://pandas.pydata.org/docs/user_guide/basics.html": "Essential Basic Functionality",
            },
        },
        "scale": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/scale.html": "Scaling to Large Datasets",
                "https://pandas.pydata.org/docs/user_guide/copy_on_write.html": "Copy-on-Write",
            },
        },
        "sparse": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/sparse.html": "Sparse Data Structures",
                "https://pandas.pydata.org/docs/reference/api/pandas.arrays.SparseArray.html": "SparseArray",
                "https://pandas.pydata.org/docs/reference/api/pandas.SparseDtype.html": "SparseDtype",
            },
        },
        "style": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/style.html": "Table Visualization (Styler)",
                "https://pandas.pydata.org/docs/reference/api/pandas.io.formats.style.Styler.html": "Styler",
                "https://pandas.pydata.org/docs/reference/api/pandas.io.formats.style.Styler.apply.html": "Styler.apply",
                "https://pandas.pydata.org/docs/reference/api/pandas.io.formats.style.Styler.map.html": "Styler.map",
                "https://pandas.pydata.org/docs/reference/api/pandas.io.formats.style.Styler.format.html": "Styler.format",
                "https://pandas.pydata.org/docs/reference/api/pandas.io.formats.style.Styler.to_html.html": "Styler.to_html",
                "https://pandas.pydata.org/docs/reference/api/pandas.io.formats.style.Styler.to_excel.html": "Styler.to_excel",
            },
        },
        "gotchas": {
            "pages": {
                "https://pandas.pydata.org/docs/user_guide/gotchas.html": "Frequently Asked Questions (FAQ)",
                "https://pandas.pydata.org/docs/user_guide/cookbook.html": "Cookbook",
            },
        },
        "api-dataframe": {
            "pages": {
                "https://pandas.pydata.org/docs/reference/frame.html": "DataFrame API Reference",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html": "pandas.DataFrame",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.head.html": "DataFrame.head",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.tail.html": "DataFrame.tail",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.info.html": "DataFrame.info",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.describe.html": "DataFrame.describe",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.shape.html": "DataFrame.shape",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.dtypes.html": "DataFrame.dtypes",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.columns.html": "DataFrame.columns",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.index.html": "DataFrame.index",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.values.html": "DataFrame.values",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.copy.html": "DataFrame.copy",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.astype.html": "DataFrame.astype",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.select_dtypes.html": "DataFrame.select_dtypes",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.drop.html": "DataFrame.drop",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rename.html": "DataFrame.rename",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.sort_values.html": "DataFrame.sort_values",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.sort_index.html": "DataFrame.sort_index",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.nlargest.html": "DataFrame.nlargest",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.nsmallest.html": "DataFrame.nsmallest",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.sample.html": "DataFrame.sample",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.replace.html": "DataFrame.replace",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.duplicated.html": "DataFrame.duplicated",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.drop_duplicates.html": "DataFrame.drop_duplicates",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.assign.html": "DataFrame.assign",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.isin.html": "DataFrame.isin",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.iterrows.html": "DataFrame.iterrows",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.itertuples.html": "DataFrame.itertuples",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_dict.html": "DataFrame.to_dict",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_numpy.html": "DataFrame.to_numpy",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_records.html": "DataFrame.to_records",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_string.html": "DataFrame.to_string",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_markdown.html": "DataFrame.to_markdown",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_latex.html": "DataFrame.to_latex",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.abs.html": "DataFrame.abs",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.clip.html": "DataFrame.clip",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.cumsum.html": "DataFrame.cumsum",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.cumprod.html": "DataFrame.cumprod",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.cummax.html": "DataFrame.cummax",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.cummin.html": "DataFrame.cummin",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.sum.html": "DataFrame.sum",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.mean.html": "DataFrame.mean",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.median.html": "DataFrame.median",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.min.html": "DataFrame.min",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.max.html": "DataFrame.max",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.std.html": "DataFrame.std",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.var.html": "DataFrame.var",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.count.html": "DataFrame.count",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.value_counts.html": "DataFrame.value_counts",
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.nunique.html": "DataFrame.nunique",
            },
        },
        "api-series": {
            "pages": {
                "https://pandas.pydata.org/docs/reference/series.html": "Series API Reference",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.html": "pandas.Series",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.values.html": "Series.values",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.dtype.html": "Series.dtype",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.name.html": "Series.name",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.map.html": "Series.map",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.apply.html": "Series.apply",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.unique.html": "Series.unique",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.value_counts.html": "Series.value_counts",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.sort_values.html": "Series.sort_values",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.astype.html": "Series.astype",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.to_frame.html": "Series.to_frame",
                "https://pandas.pydata.org/docs/reference/api/pandas.Series.to_list.html": "Series.to_list",
            },
        },
        "api-index": {
            "pages": {
                "https://pandas.pydata.org/docs/reference/indexing.html": "Index API Reference",
                "https://pandas.pydata.org/docs/reference/api/pandas.RangeIndex.html": "RangeIndex",
                "https://pandas.pydata.org/docs/reference/api/pandas.IntervalIndex.html": "IntervalIndex",
                "https://pandas.pydata.org/docs/reference/api/pandas.MultiIndex.from_tuples.html": "MultiIndex.from_tuples",
                "https://pandas.pydata.org/docs/reference/api/pandas.MultiIndex.from_arrays.html": "MultiIndex.from_arrays",
                "https://pandas.pydata.org/docs/reference/api/pandas.MultiIndex.from_product.html": "MultiIndex.from_product",
            },
        },
        "api-general": {
            "pages": {
                "https://pandas.pydata.org/docs/reference/general_functions.html": "General Functions",
                "https://pandas.pydata.org/docs/reference/api/pandas.array.html": "pandas.array",
                "https://pandas.pydata.org/docs/reference/api/pandas.from_dummies.html": "from_dummies",
                "https://pandas.pydata.org/docs/reference/api/pandas.factorize.html": "factorize",
                "https://pandas.pydata.org/docs/reference/api/pandas.unique.html": "pandas.unique",
                "https://pandas.pydata.org/docs/reference/api/pandas.cut.html": "pandas.cut",
                "https://pandas.pydata.org/docs/reference/api/pandas.qcut.html": "pandas.qcut",
                "https://pandas.pydata.org/docs/reference/api/pandas.wide_to_long.html": "wide_to_long",
                "https://pandas.pydata.org/docs/reference/api/pandas.testing.assert_frame_equal.html": "assert_frame_equal",
                "https://pandas.pydata.org/docs/reference/api/pandas.testing.assert_series_equal.html": "assert_series_equal",
                "https://pandas.pydata.org/docs/reference/api/pandas.show_versions.html": "show_versions",
            },
        },
        "api-extensions": {
            "pages": {
                "https://pandas.pydata.org/docs/reference/extensions.html": "Extension Types",
                "https://pandas.pydata.org/docs/development/extending.html": "Extending pandas",
                "https://pandas.pydata.org/docs/reference/api/pandas.api.types.is_numeric_dtype.html": "is_numeric_dtype",
                "https://pandas.pydata.org/docs/reference/api/pandas.api.types.is_string_dtype.html": "is_string_dtype",
                "https://pandas.pydata.org/docs/reference/api/pandas.api.types.is_datetime64_dtype.html": "is_datetime64_dtype",
                "https://pandas.pydata.org/docs/reference/api/pandas.api.types.is_categorical_dtype.html": "is_categorical_dtype",
                "https://pandas.pydata.org/docs/reference/api/pandas.api.types.is_bool_dtype.html": "is_bool_dtype",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"pandas-{source_key}" if source_key else "pandas"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Clean common suffixes
            for suffix in [' -- pandas documentation', ' - pandas', ' pandas', ' | pandas']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})

        for url, title in pages.items():
            if not self.running:
                break

            item_id = self.make_id(url)
            content = self.fetch_url(url)

            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)

                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"pandas-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)

        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0

        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(
                    f"Unknown source key: {self.source_key}. "
                    f"Available: {list(self.SOURCES.keys())}"
                )
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES

        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping pandas/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    PandasScraper(base, source_key).run()
