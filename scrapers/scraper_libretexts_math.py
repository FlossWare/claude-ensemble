#!/usr/bin/env python3
"""Mathematics LibreTexts documentation scraper.

Covers:
  - Algebra (elementary through intermediate) - equations, polynomials, systems
  - Precalculus (OpenStax) - functions, trigonometry, analytic geometry
  - Calculus I/II/III (OpenStax) - limits, derivatives, integrals, multivariable
  - Differential Equations (Herman) - ODEs, Laplace transforms, systems
  - Linear Algebra (Kuttler) - matrices, determinants, vector spaces, eigenvalues
  - Discrete Mathematics (Kwong) - logic, sets, combinatorics, graph theory
  - Abstract Algebra (Judson) - groups, rings, fields, Galois theory
  - Real Analysis (Trench) - sequences, continuity, metric spaces
  - Probability and Statistics - distributions, hypothesis testing, regression
  - Additional bookshelf pages for geometry, number theory, applied math
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class LibreTextsMathScraper(BaseScraper):
    SOURCES = {
        "algebra": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Algebra": "Algebra Bookshelf",
                "https://math.libretexts.org/Bookshelves/Algebra/Elementary_Algebra_(Ellis_and_Burzynski)/01%3A_Arithmetic_Review": "Arithmetic Review",
                "https://math.libretexts.org/Bookshelves/Algebra/Elementary_Algebra_(Ellis_and_Burzynski)/02%3A_Basic_Properties_of_Real_Numbers": "Basic Properties of Real Numbers",
                "https://math.libretexts.org/Bookshelves/Algebra/Elementary_Algebra_(Ellis_and_Burzynski)/03%3A_Basic_Operations_with_Real_Numbers": "Basic Operations with Real Numbers",
                "https://math.libretexts.org/Bookshelves/Algebra/Elementary_Algebra_(Ellis_and_Burzynski)/04%3A_Algebraic_Expressions_and_Equations": "Algebraic Expressions and Equations",
                "https://math.libretexts.org/Bookshelves/Algebra/Elementary_Algebra_(Ellis_and_Burzynski)/05%3A_Solving_Linear_Equations_and_Inequalities": "Solving Linear Equations and Inequalities",
                "https://math.libretexts.org/Bookshelves/Algebra/Elementary_Algebra_(Ellis_and_Burzynski)/06%3A_Factoring_Polynomials": "Factoring Polynomials",
                "https://math.libretexts.org/Bookshelves/Algebra/Elementary_Algebra_(Ellis_and_Burzynski)/07%3A_Graphing_Linear_Equations_and_Inequalities_in_One_and_Two_Variables": "Graphing Linear Equations",
                "https://math.libretexts.org/Bookshelves/Algebra/Elementary_Algebra_(Ellis_and_Burzynski)/08%3A_Rational_Expressions": "Rational Expressions",
                "https://math.libretexts.org/Bookshelves/Algebra/Elementary_Algebra_(Ellis_and_Burzynski)/09%3A_Roots_Radicals_and_Square_Root_Equations": "Roots, Radicals, and Square Root Equations",
                "https://math.libretexts.org/Bookshelves/Algebra/Elementary_Algebra_(Ellis_and_Burzynski)/10%3A_Quadratic_Equations": "Quadratic Equations",
                "https://math.libretexts.org/Bookshelves/Algebra/Elementary_Algebra_(Ellis_and_Burzynski)/11%3A_Systems_of_Linear_Equations": "Systems of Linear Equations",
            },
        },
        "precalculus": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Precalculus": "Precalculus Bookshelf",
                "https://math.libretexts.org/Bookshelves/Precalculus/Precalculus_1e_(OpenStax)/01%3A_Functions": "Functions",
                "https://math.libretexts.org/Bookshelves/Precalculus/Precalculus_1e_(OpenStax)/02%3A_Linear_Functions": "Linear Functions",
                "https://math.libretexts.org/Bookshelves/Precalculus/Precalculus_1e_(OpenStax)/03%3A_Polynomial_and_Rational_Functions": "Polynomial and Rational Functions",
                "https://math.libretexts.org/Bookshelves/Precalculus/Precalculus_1e_(OpenStax)/04%3A_Exponential_and_Logarithmic_Functions": "Exponential and Logarithmic Functions",
                "https://math.libretexts.org/Bookshelves/Precalculus/Precalculus_1e_(OpenStax)/05%3A_Trigonometric_Functions": "Trigonometric Functions",
                "https://math.libretexts.org/Bookshelves/Precalculus/Precalculus_1e_(OpenStax)/06%3A_Periodic_Functions": "Periodic Functions",
                "https://math.libretexts.org/Bookshelves/Precalculus/Precalculus_1e_(OpenStax)/07%3A_Trigonometric_Identities_and_Equations": "Trigonometric Identities and Equations",
                "https://math.libretexts.org/Bookshelves/Precalculus/Precalculus_1e_(OpenStax)/08%3A_Further_Applications_of_Trigonometry": "Further Applications of Trigonometry",
                "https://math.libretexts.org/Bookshelves/Precalculus/Precalculus_1e_(OpenStax)/09%3A_Systems_of_Equations_and_Inequalities": "Systems of Equations and Inequalities",
                "https://math.libretexts.org/Bookshelves/Precalculus/Precalculus_1e_(OpenStax)/10%3A_Analytic_Geometry": "Analytic Geometry",
                "https://math.libretexts.org/Bookshelves/Precalculus/Precalculus_1e_(OpenStax)/11%3A_Sequences_Probability_and_Counting_Theory": "Sequences, Probability and Counting Theory",
                "https://math.libretexts.org/Bookshelves/Precalculus/Precalculus_1e_(OpenStax)/12%3A_Introduction_to_Calculus": "Introduction to Calculus",
                "https://math.libretexts.org/Bookshelves/Precalculus/Precalculus_1e_(OpenStax)/13%3A_Trigonometric_Functions": "Trigonometric Functions (Chapter 13)",
            },
        },
        "calculus": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Calculus": "Calculus Bookshelf",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/01%3A_Functions_and_Graphs": "Functions and Graphs",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/02%3A_Limits": "Limits",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/03%3A_Derivatives": "Derivatives",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/04%3A_Applications_of_Derivatives": "Applications of Derivatives",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/05%3A_Integration": "Integration",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/06%3A_Applications_of_Integration": "Applications of Integration",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/07%3A_Techniques_of_Integration": "Techniques of Integration",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/08%3A_Introduction_to_Differential_Equations": "Introduction to Differential Equations",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/09%3A_Sequences_and_Series": "Sequences and Series",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/10%3A_Power_Series": "Power Series",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/11%3A_Parametric_Equations_and_Polar_Coordinates": "Parametric Equations and Polar Coordinates",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/12%3A_Vectors_in_Space": "Vectors in Space",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/13%3A_Vector-Valued_Functions": "Vector-Valued Functions",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/14%3A_Differentiation_of_Functions_of_Several_Variables": "Differentiation of Functions of Several Variables",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/15%3A_Multiple_Integration": "Multiple Integration",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/16%3A_Vector_Calculus": "Vector Calculus",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)/17%3A_Second-Order_Differential_Equations": "Second-Order Differential Equations",
            },
        },
        "differential-equations": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Differential_Equations": "Differential Equations Bookshelf",
                "https://math.libretexts.org/Bookshelves/Differential_Equations/A_First_Course_in_Differential_Equations_for_Scientists_and_Engineers_(Herman)/01%3A_First_Order_ODEs": "First Order ODEs",
                "https://math.libretexts.org/Bookshelves/Differential_Equations/A_First_Course_in_Differential_Equations_for_Scientists_and_Engineers_(Herman)/02%3A_Second_Order_ODEs": "Second Order ODEs",
                "https://math.libretexts.org/Bookshelves/Differential_Equations/A_First_Course_in_Differential_Equations_for_Scientists_and_Engineers_(Herman)/03%3A_Numerical_Solutions": "Numerical Solutions",
                "https://math.libretexts.org/Bookshelves/Differential_Equations/A_First_Course_in_Differential_Equations_for_Scientists_and_Engineers_(Herman)/04%3A_Series_Solutions": "Series Solutions",
                "https://math.libretexts.org/Bookshelves/Differential_Equations/A_First_Course_in_Differential_Equations_for_Scientists_and_Engineers_(Herman)/05%3A_Laplace_Transforms": "Laplace Transforms",
                "https://math.libretexts.org/Bookshelves/Differential_Equations/A_First_Course_in_Differential_Equations_for_Scientists_and_Engineers_(Herman)/06%3A_Linear_Systems": "Linear Systems",
                "https://math.libretexts.org/Bookshelves/Differential_Equations/A_First_Course_in_Differential_Equations_for_Scientists_and_Engineers_(Herman)/07%3A_Nonlinear_Systems": "Nonlinear Systems",
            },
        },
        "linear-algebra": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Linear_Algebra": "Linear Algebra Bookshelf",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/A_First_Course_in_Linear_Algebra_(Kuttler)/01%3A_Systems_of_Equations": "Systems of Equations",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/A_First_Course_in_Linear_Algebra_(Kuttler)/02%3A_Matrices": "Matrices",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/A_First_Course_in_Linear_Algebra_(Kuttler)/03%3A_Determinants": "Determinants",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/A_First_Course_in_Linear_Algebra_(Kuttler)/04%3A_R": "Rn",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/A_First_Course_in_Linear_Algebra_(Kuttler)/05%3A_Linear_Transformations": "Linear Transformations",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/A_First_Course_in_Linear_Algebra_(Kuttler)/06%3A_Complex_Numbers": "Complex Numbers",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/A_First_Course_in_Linear_Algebra_(Kuttler)/07%3A_Spectral_Theory": "Spectral Theory",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/A_First_Course_in_Linear_Algebra_(Kuttler)/08%3A_Some_Curvilinear_Coordinate_Systems": "Some Curvilinear Coordinate Systems",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/A_First_Course_in_Linear_Algebra_(Kuttler)/09%3A_Vector_Spaces": "Vector Spaces",
            },
        },
        "discrete-math": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics": "Discrete Mathematics Bookshelf",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/A_Spiral_Workbook_for_Discrete_Mathematics_(Kwong)/01%3A_Introduction_to_Discrete_Mathematics": "Introduction to Discrete Mathematics",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/A_Spiral_Workbook_for_Discrete_Mathematics_(Kwong)/02%3A_Logic": "Logic",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/A_Spiral_Workbook_for_Discrete_Mathematics_(Kwong)/03%3A_Proof_Techniques": "Proof Techniques",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/A_Spiral_Workbook_for_Discrete_Mathematics_(Kwong)/04%3A_Sets": "Sets",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/A_Spiral_Workbook_for_Discrete_Mathematics_(Kwong)/05%3A_Basic_Number_Theory": "Basic Number Theory",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/A_Spiral_Workbook_for_Discrete_Mathematics_(Kwong)/06%3A_Functions": "Functions",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/A_Spiral_Workbook_for_Discrete_Mathematics_(Kwong)/07%3A_Relations": "Relations",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/A_Spiral_Workbook_for_Discrete_Mathematics_(Kwong)/08%3A_Combinatorics": "Combinatorics",
            },
        },
        "abstract-algebra": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra": "Abstract and Geometric Algebra Bookshelf",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/01%3A_Preliminaries": "Preliminaries",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/02%3A_The_Integers": "The Integers",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/03%3A_Groups": "Groups",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/04%3A_Cyclic_Groups": "Cyclic Groups",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/05%3A_Permutation_Groups": "Permutation Groups",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/06%3A_Cosets_and_Lagrange's_Theorem": "Cosets and Lagrange's Theorem",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/07%3A_Introduction_to_Cryptography": "Introduction to Cryptography",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/08%3A_Algebraic_Coding_Theory": "Algebraic Coding Theory",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/09%3A_Isomorphisms": "Isomorphisms",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/10%3A_Normal_Subgroups_and_Factor_Groups": "Normal Subgroups and Factor Groups",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/11%3A_Homomorphisms": "Homomorphisms",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/12%3A_Matrix_Groups_and_Symmetry": "Matrix Groups and Symmetry",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/13%3A_The_Structure_of_Groups": "The Structure of Groups",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/14%3A_Group_Actions": "Group Actions",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/15%3A_The_Sylow_Theorems": "The Sylow Theorems",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/16%3A_Rings": "Rings",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/17%3A_Polynomials": "Polynomials",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/18%3A_Integral_Domains": "Integral Domains",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/19%3A_Lattices_and_Boolean_Algebras": "Lattices and Boolean Algebras",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/20%3A_Vector_Spaces": "Vector Spaces",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/21%3A_Fields": "Fields",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/22%3A_Finite_Fields": "Finite Fields",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)/23%3A_Galois_Theory": "Galois Theory",
            },
        },
        "real-analysis": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Analysis": "Analysis Bookshelf",
                "https://math.libretexts.org/Bookshelves/Analysis/Introduction_to_Real_Analysis_(Trench)/01%3A_The_Real_Numbers": "The Real Numbers",
                "https://math.libretexts.org/Bookshelves/Analysis/Introduction_to_Real_Analysis_(Trench)/02%3A_Differential_Calculus_of_Functions_of_One_Variable": "Differential Calculus",
                "https://math.libretexts.org/Bookshelves/Analysis/Introduction_to_Real_Analysis_(Trench)/03%3A_Integral_Calculus_of_Functions_of_One_Variable": "Integral Calculus",
                "https://math.libretexts.org/Bookshelves/Analysis/Introduction_to_Real_Analysis_(Trench)/04%3A_Infinite_Sequences_and_Series": "Infinite Sequences and Series",
                "https://math.libretexts.org/Bookshelves/Analysis/Introduction_to_Real_Analysis_(Trench)/05%3A_Real-Valued_Functions_of_Several_Variables": "Real-Valued Functions of Several Variables",
                "https://math.libretexts.org/Bookshelves/Analysis/Introduction_to_Real_Analysis_(Trench)/06%3A_Vector-Valued_Functions_of_Several_Variables": "Vector-Valued Functions of Several Variables",
                "https://math.libretexts.org/Bookshelves/Analysis/Introduction_to_Real_Analysis_(Trench)/07%3A_Integrals_of_Functions_of_Several_Variables": "Integrals of Functions of Several Variables",
                "https://math.libretexts.org/Bookshelves/Analysis/Introduction_to_Real_Analysis_(Trench)/08%3A_Metric_Spaces": "Metric Spaces",
            },
        },
        "probability-statistics": {
            "pages": {
                "https://stats.libretexts.org/Bookshelves": "Statistics Bookshelves",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics": "Introductory Statistics",
                "https://stats.libretexts.org/Bookshelves/Probability_Theory": "Probability Theory",
                "https://stats.libretexts.org/Bookshelves/Applied_Statistics": "Applied Statistics",
                "https://stats.libretexts.org/Bookshelves/Advanced_Statistics": "Advanced Statistics",
                "https://stats.libretexts.org/Bookshelves/Computing_and_Modeling": "Computing and Modeling",
                "https://math.libretexts.org/Bookshelves/Applied_Mathematics": "Applied Mathematics Bookshelf",
                "https://math.libretexts.org/Bookshelves/Scientific_Computing_Simulations_and_Modeling": "Scientific Computing",
                "https://math.libretexts.org/Bookshelves/Mathematical_Logic_and_Proof": "Mathematical Logic",
            },
        },
        "intermediate-algebra": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Algebra/Intermediate_Algebra_(OpenStax)": "Intermediate Algebra (OpenStax)",
                "https://math.libretexts.org/Bookshelves/Algebra/Intermediate_Algebra_(OpenStax)/01%3A_Foundations": "Foundations",
                "https://math.libretexts.org/Bookshelves/Algebra/Intermediate_Algebra_(OpenStax)/02%3A_Solving_Linear_Equations_and_Inequalities": "Solving Linear Equations and Inequalities",
                "https://math.libretexts.org/Bookshelves/Algebra/Intermediate_Algebra_(OpenStax)/03%3A_Graphs": "Graphs",
                "https://math.libretexts.org/Bookshelves/Algebra/Intermediate_Algebra_(OpenStax)/04%3A_Systems_of_Linear_Equations": "Systems of Linear Equations",
                "https://math.libretexts.org/Bookshelves/Algebra/Intermediate_Algebra_(OpenStax)/05%3A_Polynomials": "Polynomials",
                "https://math.libretexts.org/Bookshelves/Algebra/Intermediate_Algebra_(OpenStax)/06%3A_Factoring": "Factoring",
                "https://math.libretexts.org/Bookshelves/Algebra/Intermediate_Algebra_(OpenStax)/07%3A_Rational_Expressions_and_Functions": "Rational Expressions and Functions",
                "https://math.libretexts.org/Bookshelves/Algebra/Intermediate_Algebra_(OpenStax)/08%3A_Roots_and_Radicals": "Roots and Radicals",
                "https://math.libretexts.org/Bookshelves/Algebra/Intermediate_Algebra_(OpenStax)/09%3A_Quadratic_Equations_and_Functions": "Quadratic Equations and Functions",
                "https://math.libretexts.org/Bookshelves/Algebra/Intermediate_Algebra_(OpenStax)/10%3A_Exponential_and_Logarithmic_Functions": "Exponential and Logarithmic Functions",
                "https://math.libretexts.org/Bookshelves/Algebra/Intermediate_Algebra_(OpenStax)/11%3A_Conics": "Conics",
                "https://math.libretexts.org/Bookshelves/Algebra/Intermediate_Algebra_(OpenStax)/12%3A_Sequences_Series_and_the_Binomial_Theorem": "Sequences, Series, and the Binomial Theorem",
            },
        },
        "college-algebra": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Algebra/College_Algebra_1e_(OpenStax)": "College Algebra (OpenStax)",
                "https://math.libretexts.org/Bookshelves/Algebra/College_Algebra_1e_(OpenStax)/01%3A_Prerequisites": "Prerequisites",
                "https://math.libretexts.org/Bookshelves/Algebra/College_Algebra_1e_(OpenStax)/02%3A_Equations_and_Inequalities": "Equations and Inequalities",
                "https://math.libretexts.org/Bookshelves/Algebra/College_Algebra_1e_(OpenStax)/03%3A_Functions": "Functions (College Algebra)",
                "https://math.libretexts.org/Bookshelves/Algebra/College_Algebra_1e_(OpenStax)/04%3A_Linear_Functions": "Linear Functions (College Algebra)",
                "https://math.libretexts.org/Bookshelves/Algebra/College_Algebra_1e_(OpenStax)/05%3A_Polynomial_and_Rational_Functions": "Polynomial and Rational Functions (College Algebra)",
                "https://math.libretexts.org/Bookshelves/Algebra/College_Algebra_1e_(OpenStax)/06%3A_Exponential_and_Logarithmic_Functions": "Exponential and Logarithmic Functions (College Algebra)",
                "https://math.libretexts.org/Bookshelves/Algebra/College_Algebra_1e_(OpenStax)/07%3A_Systems_of_Equations_and_Inequalities": "Systems of Equations and Inequalities (College Algebra)",
                "https://math.libretexts.org/Bookshelves/Algebra/College_Algebra_1e_(OpenStax)/08%3A_Analytic_Geometry": "Analytic Geometry (College Algebra)",
                "https://math.libretexts.org/Bookshelves/Algebra/College_Algebra_1e_(OpenStax)/09%3A_Sequences_Probability_and_Counting_Theory": "Sequences, Probability, and Counting Theory",
            },
        },
        "intro-statistics": {
            "pages": {
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(OpenStax)": "Introductory Statistics (OpenStax)",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(OpenStax)/01%3A_Sampling_and_Data": "Sampling and Data",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(OpenStax)/02%3A_Descriptive_Statistics": "Descriptive Statistics",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(OpenStax)/03%3A_Probability_Topics": "Probability Topics",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(OpenStax)/04%3A_Discrete_Random_Variables": "Discrete Random Variables",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(OpenStax)/05%3A_Continuous_Random_Variables": "Continuous Random Variables",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(OpenStax)/06%3A_The_Normal_Distribution": "The Normal Distribution",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(OpenStax)/07%3A_The_Central_Limit_Theorem": "The Central Limit Theorem",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(OpenStax)/08%3A_Confidence_Intervals": "Confidence Intervals",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(OpenStax)/09%3A_Hypothesis_Testing_with_One_Sample": "Hypothesis Testing with One Sample",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(OpenStax)/10%3A_Hypothesis_Testing_with_Two_Samples": "Hypothesis Testing with Two Samples",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(OpenStax)/11%3A_The_Chi-Square_Distribution": "The Chi-Square Distribution",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(OpenStax)/12%3A_Linear_Regression_and_Correlation": "Linear Regression and Correlation",
                "https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(OpenStax)/13%3A_F_Distribution_and_One-Way_ANOVA": "F Distribution and One-Way ANOVA",
            },
        },
        "geometry": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Geometry": "Geometry Bookshelf",
                "https://math.libretexts.org/Bookshelves/Geometry/Elementary_College_Geometry_(Africk)": "Elementary College Geometry",
                "https://math.libretexts.org/Bookshelves/Geometry/Elementary_College_Geometry_(Africk)/01%3A_Lines_Angles_and_Triangles": "Lines, Angles, and Triangles",
                "https://math.libretexts.org/Bookshelves/Geometry/Elementary_College_Geometry_(Africk)/02%3A_Congruent_Triangles": "Congruent Triangles",
                "https://math.libretexts.org/Bookshelves/Geometry/Elementary_College_Geometry_(Africk)/03%3A_Quadrilaterals": "Quadrilaterals",
                "https://math.libretexts.org/Bookshelves/Geometry/Elementary_College_Geometry_(Africk)/04%3A_Similar_Triangles": "Similar Triangles",
                "https://math.libretexts.org/Bookshelves/Geometry/Elementary_College_Geometry_(Africk)/05%3A_Trigonometry_and_Right_Triangles": "Trigonometry and Right Triangles",
                "https://math.libretexts.org/Bookshelves/Geometry/Elementary_College_Geometry_(Africk)/06%3A_Area_and_Perimeter": "Area and Perimeter",
                "https://math.libretexts.org/Bookshelves/Geometry/Elementary_College_Geometry_(Africk)/07%3A_Regular_Polygons_and_Circles": "Regular Polygons and Circles",
            },
        },
        "additional-analysis": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Analysis/Mathematical_Analysis_(Zakon)": "Mathematical Analysis (Zakon)",
                "https://math.libretexts.org/Bookshelves/Analysis/Introduction_to_Mathematical_Analysis_I_(Lafferriere_Lafferriere_and_Nguyen)": "Introduction to Mathematical Analysis I",
                "https://math.libretexts.org/Bookshelves/Analysis/Real_Analysis_(Boman_and_Rogers)": "Real Analysis (Boman and Rogers)",
                "https://math.libretexts.org/Bookshelves/Analysis/A_Primer_of_Real_Analysis_(Sloughter)": "A Primer of Real Analysis",
                "https://math.libretexts.org/Bookshelves/Analysis/Complex_Variables_with_Applications_(Orloff)": "Complex Variables with Applications",
                "https://math.libretexts.org/Bookshelves/Analysis/Tasty_Bits_of_Several_Complex_Variables_(Lebl)": "Tasty Bits of Several Complex Variables",
                "https://math.libretexts.org/Bookshelves/Analysis/Complex_Analysis_-_A_Visual_and_Interactive_Introduction_(Ponce_Campuzano)": "Complex Analysis: Visual and Interactive",
                "https://math.libretexts.org/Bookshelves/Analysis/Functions_Defined_by_Improper_Integrals_(Trench)": "Functions Defined by Improper Integrals",
                "https://math.libretexts.org/Bookshelves/Analysis/Supplemental_Modules_(Analysis)": "Supplemental Modules (Analysis)",
            },
        },
        "additional-diffeq": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Differential_Equations/A_First_Course_in_Differential_Equations_for_Scientists_and_Engineers_(Herman)": "DE for Scientists and Engineers Landing",
                "https://math.libretexts.org/Bookshelves/Differential_Equations/Differential_Equations_(Chasnov)": "Differential Equations (Chasnov)",
                "https://math.libretexts.org/Bookshelves/Differential_Equations/Elementary_Differential_Equations_with_Boundary_Value_Problems_(Trench)": "Elementary DE with BVP (Trench)",
                "https://math.libretexts.org/Bookshelves/Differential_Equations/Differential_Equations_for_Engineers_(Lebl)": "DE for Engineers (Lebl)",
                "https://math.libretexts.org/Bookshelves/Differential_Equations/Introduction_to_Partial_Differential_Equations_(Herman)": "Introduction to PDEs",
                "https://math.libretexts.org/Bookshelves/Differential_Equations/A_First_Course_in_Differential_Equations_for_Scientists_and_Engineers_(Herman)/08%3A_Appendix_Calculus_Review": "Appendix Calculus Review",
            },
        },
        "additional-linear-algebra": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/A_First_Course_in_Linear_Algebra_(Kuttler)": "First Course in Linear Algebra Landing",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/A_First_Course_in_Linear_Algebra_(Kuttler)/10%3A_Some_Prerequisite_Topics": "Some Prerequisite Topics",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/Interactive_Linear_Algebra_(Margalit_and_Rabinoff)": "Interactive Linear Algebra",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/Linear_Algebra_with_Applications_(Nicholson)": "Linear Algebra with Applications",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/Map%3A_Linear_Algebra_(Waldron_Cherney_and_Denton)": "Linear Algebra (Waldron, Cherney, Denton)",
                "https://math.libretexts.org/Bookshelves/Linear_Algebra/Matrix_Algebra_with_Computational_Applications_(Colbry)": "Matrix Algebra with Computational Applications",
            },
        },
        "prealgebra": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/PreAlgebra": "Pre-Algebra Bookshelf",
                "https://math.libretexts.org/Bookshelves/PreAlgebra/Prealgebra_1e_(OpenStax)": "Prealgebra (OpenStax)",
                "https://math.libretexts.org/Bookshelves/PreAlgebra/Prealgebra_1e_(OpenStax)/01%3A_Whole_Numbers": "Whole Numbers",
                "https://math.libretexts.org/Bookshelves/PreAlgebra/Prealgebra_1e_(OpenStax)/02%3A_The_Language_of_Algebra": "The Language of Algebra",
                "https://math.libretexts.org/Bookshelves/PreAlgebra/Prealgebra_1e_(OpenStax)/03%3A_Integers": "Integers",
                "https://math.libretexts.org/Bookshelves/PreAlgebra/Prealgebra_1e_(OpenStax)/04%3A_Fractions": "Fractions",
                "https://math.libretexts.org/Bookshelves/PreAlgebra/Prealgebra_1e_(OpenStax)/05%3A_Decimals": "Decimals",
                "https://math.libretexts.org/Bookshelves/PreAlgebra/Prealgebra_1e_(OpenStax)/06%3A_Percents": "Percents",
                "https://math.libretexts.org/Bookshelves/PreAlgebra/Prealgebra_1e_(OpenStax)/07%3A_The_Properties_of_Real_Numbers": "Properties of Real Numbers",
                "https://math.libretexts.org/Bookshelves/PreAlgebra/Prealgebra_1e_(OpenStax)/08%3A_Solving_Linear_Equations": "Solving Linear Equations (PreAlgebra)",
                "https://math.libretexts.org/Bookshelves/PreAlgebra/Prealgebra_1e_(OpenStax)/09%3A_Math_Models_and_Geometry": "Math Models and Geometry",
                "https://math.libretexts.org/Bookshelves/Arithmetic_and_Basic_Math": "Arithmetic and Basic Math Bookshelf",
            },
        },
        "trigonometry": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Precalculus/Elementary_Trigonometry_(Corral)": "Elementary Trigonometry (Corral)",
                "https://math.libretexts.org/Bookshelves/Precalculus/Elementary_Trigonometry_(Corral)/01%3A_Right_Triangle_Trigonometry_Angles": "Right Triangle Trigonometry",
                "https://math.libretexts.org/Bookshelves/Precalculus/Elementary_Trigonometry_(Corral)/02%3A_General_Triangles": "General Triangles",
                "https://math.libretexts.org/Bookshelves/Precalculus/Elementary_Trigonometry_(Corral)/03%3A_Identities": "Trigonometric Identities",
                "https://math.libretexts.org/Bookshelves/Precalculus/Elementary_Trigonometry_(Corral)/04%3A_Radian_Measure": "Radian Measure",
                "https://math.libretexts.org/Bookshelves/Precalculus/Elementary_Trigonometry_(Corral)/05%3A_Graphing_and_Inverse_Functions": "Graphing and Inverse Functions",
                "https://math.libretexts.org/Bookshelves/Precalculus/Elementary_Trigonometry_(Corral)/06%3A_Additional_Topics": "Additional Trigonometry Topics",
            },
        },
        "number-theory": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/Elementary_Number_Theory_(Raji)": "Elementary Number Theory (Raji)",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/Elementary_Number_Theory_(Raji)/01%3A_Introduction": "Introduction to Number Theory",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/Elementary_Number_Theory_(Raji)/02%3A_Prime_Numbers": "Prime Numbers",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/Elementary_Number_Theory_(Raji)/03%3A_Congruences": "Congruences",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/Elementary_Number_Theory_(Raji)/04%3A_Multiplicative_Number_Theoretic_Functions": "Multiplicative Functions",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/Elementary_Number_Theory_(Raji)/05%3A_Primitive_Roots_and_Indices": "Primitive Roots and Indices",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/Elementary_Number_Theory_(Raji)/06%3A_Quadratic_Residues": "Quadratic Residues",
            },
        },
        "graph-theory": {
            "pages": {
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/Combinatorics_and_Graph_Theory_(Guichard)": "Combinatorics and Graph Theory (Guichard)",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/Combinatorics_and_Graph_Theory_(Guichard)/01%3A_Fundamentals": "Fundamentals of Combinatorics",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/Combinatorics_and_Graph_Theory_(Guichard)/02%3A_Inclusion-Exclusion": "Inclusion-Exclusion",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/Combinatorics_and_Graph_Theory_(Guichard)/03%3A_Generating_Functions": "Generating Functions",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/Combinatorics_and_Graph_Theory_(Guichard)/04%3A_Graph_Theory": "Graph Theory",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/Combinatorics_and_Graph_Theory_(Guichard)/05%3A_Ramsey_Theory": "Ramsey Theory",
            },
        },
        "bookshelves": {
            "pages": {
                "https://math.libretexts.org/Bookshelves": "Mathematics Bookshelves Home",
                "https://math.libretexts.org/Bookshelves/Calculus/Calculus_(OpenStax)": "Calculus (OpenStax) Landing",
                "https://math.libretexts.org/Bookshelves/Precalculus/Precalculus_1e_(OpenStax)": "Precalculus (OpenStax) Landing",
                "https://math.libretexts.org/Bookshelves/Algebra/Elementary_Algebra_(Ellis_and_Burzynski)": "Elementary Algebra Landing",
                "https://math.libretexts.org/Bookshelves/Abstract_and_Geometric_Algebra/Abstract_Algebra%3A_Theory_and_Applications_(Judson)": "Abstract Algebra (Judson) Landing",
                "https://math.libretexts.org/Bookshelves/Analysis/Introduction_to_Real_Analysis_(Trench)": "Real Analysis (Trench) Landing",
                "https://math.libretexts.org/Bookshelves/Combinatorics_and_Discrete_Mathematics/A_Spiral_Workbook_for_Discrete_Mathematics_(Kwong)": "Discrete Math (Kwong) Landing",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"libretexts-math-{source_key}" if source_key else "libretexts-math"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
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
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [' - Mathematics LibreTexts', ' - LibreTexts', ' | LibreTexts']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
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
                        "category": f"libretexts-math-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")
            time.sleep(1.5)
        return count

    def scrape(self):
        total = 0
        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(f"Unknown source key: {self.source_key}. Available: {list(self.SOURCES.keys())}")
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES
        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping libretexts-math/{key} ===")
            total += self._scrape_source(key, config)
        return total

if __name__ == "__main__":
    import os
    import sys
    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    LibreTextsMathScraper(base, source_key).run()
