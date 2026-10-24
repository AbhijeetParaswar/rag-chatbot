"""Generate realistic sample PDF documents for testing the RAG chatbot."""

from pathlib import Path
import fitz  # PyMuPDF


def create_sample_pdfs():
    out_dir = Path("data/pdfs")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Course Syllabus
    doc1 = fitz.open()
    # Page 1
    p1 = doc1.new_page()
    p1.insert_text(
        (50, 70),
        "CS 101: Introduction to Computer Science & Algorithms\n"
        "Fall Semester 2026 - Department of Computer Science\n"
        "Instructor: Prof. Alan Turing (aturing@university.edu)\n"
        "Office Hours: Tuesdays & Thursdays 2:00 PM - 4:00 PM, Turing Hall Room 402\n\n"
        "Section 1. Course Overview and Prerequisites\n"
        "This course introduces fundamental algorithmic thinking, data structures, and computational complexity.\n"
        "Students will master recursion, sorting algorithms (MergeSort, QuickSort), graph traversals (BFS, DFS),\n"
        "and basic dynamic programming. Prerequisites: High school mathematics and basic programming literacy.\n\n"
        "Section 2. Grading Breakdown and Criteria\n"
        "Final grades are determined by the following weighted components:\n"
        "- Programming Assignments (5 total): 30%\n"
        "- Midterm Examination: 25% (Held in Week 8)\n"
        "- Comprehensive Final Examination: 35% (Held during exam week)\n"
        "- Class Attendance & Discussion Participation: 10%\n"
        "Grading Scale: A: 90-100%, B: 80-89%, C: 70-79%, D: 60-69%, F: below 60%.\n",
        fontsize=11,
    )
    # Page 2
    p2 = doc1.new_page()
    p2.insert_text(
        (50, 70),
        "CS 101: Course Policies and Schedule\n\n"
        "Section 3. Late Submission and Extension Policy\n"
        "Assignments submitted after the deadline will incur a penalty of 10% per 24-hour period of lateness.\n"
        "Submissions more than 72 hours (3 days) late will receive an automatic grade of 0.\n"
        "Each student is granted two (2) 'Slip Days' for the semester, which can be applied to any programming\n"
        "assignment without penalty. Medical emergencies require documentation from Student Health Services.\n\n"
        "Section 4. Recommended Textbooks and Resources\n"
        "Required: 'Introduction to Algorithms' by Cormen, Leiserson, Rivest, and Stein (CLRS), 4th Edition.\n"
        "Optional: 'Algorithms' by Robert Sedgewick and Kevin Wayne.\n"
        "All assignments must be tested on Python 3.11 before submission.\n",
        fontsize=11,
    )
    doc1.save(str(out_dir / "cs101_syllabus.pdf"))
    doc1.close()
    print("Created cs101_syllabus.pdf")

    # 2. Academic Integrity Policy
    doc2 = fitz.open()
    # Page 1
    p1 = doc2.new_page()
    p1.insert_text(
        (50, 70),
        "University Academic Integrity Policy & Code of Student Conduct\n"
        "Office of the Dean of Academic Affairs - Effective Academic Year 2025-2026\n\n"
        "Section 1. Core Principles of Academic Honesty\n"
        "Academic integrity is the cornerstone of scholarly inquiry. Every student agrees to produce original work,\n"
        "acknowledge intellectual debts properly, and uphold ethical conduct in examinations and research.\n\n"
        "Section 2. Violations and Definitions of Misconduct\n"
        "The following behaviors constitute severe violations of university standards:\n"
        "1. Plagiarism: Submitting another author's work, code, or ideas as one's own without appropriate citation.\n"
        "2. Unauthorized Collaboration: Working together on individual problem sets or programming tasks without explicit instructor permission.\n"
        "3. Contract Cheating: Purchasing or soliciting commercial homework completion or essay writing services.\n"
        "4. Unauthorized AI Usage: Using large language models to generate solutions when prohibited by course policy.\n",
        fontsize=11,
    )
    # Page 2
    p2 = doc2.new_page()
    p2.insert_text(
        (50, 70),
        "University Academic Integrity Policy: Sanctions and Appeals\n\n"
        "Section 3. Disciplinary Sanctions\n"
        "Upon confirmation of an academic integrity violation, sanctions may include:\n"
        "- First Offense: Failure on the assignment (grade of zero) and official reprimand placed in student dossier.\n"
        "- Egregious or Second Offense: Immediate grade of 'XF' (failure due to academic dishonesty) in the course.\n"
        "- Third Offense or Gross Misconduct: Permanent expulsion from the university.\n\n"
        "Section 4. Student Appeals Procedure\n"
        "A student has the right to appeal any disciplinary finding to the Academic Integrity Board.\n"
        "Appeals must be lodged in writing within ten (10) business days following receipt of the official decision.\n"
        "Hearings will be convened within twenty (20) business days of appeal submission.\n",
        fontsize=11,
    )
    doc2.save(str(out_dir / "academic_integrity_policy.pdf"))
    doc2.close()
    print("Created academic_integrity_policy.pdf")

    # 3. Deep Learning Survey Paper
    doc3 = fitz.open()
    # Page 1
    p1 = doc3.new_page()
    p1.insert_text(
        (50, 70),
        "A Comprehensive Survey on Attention Mechanisms in Modern Deep Learning\n"
        "Dr. Elena Rostova & Dr. Marcus Chen - AI Research Institute\n\n"
        "Section 1. Introduction to Attention and Sequence Modeling\n"
        "Traditional Recurrent Neural Networks (RNNs) and LSTMs suffered from catastrophic forgetting and bottlenecked\n"
        "hidden states when processing long sequences. The introduction of the Transformer architecture by Vaswani et al.\n"
        "revolutionized sequence modeling by replacing recurrence entirely with Scaled Dot-Product Attention.\n"
        "Attention computes a weighted representation where queries (Q), keys (K), and values (V) interact via matrix multiplications.\n\n"
        "Section 2. Multi-Head Attention Architecture\n"
        "Rather than computing a single attention function, Multi-Head Attention projects queries, keys, and values\n"
        "into h distinct subspaces. This allows the model to jointly attend to information from different representation\n"
        "subspaces at different positions. Mathematical formulation: Attention(Q, K, V) = softmax((Q K^T) / sqrt(d_k)) V.\n",
        fontsize=11,
    )
    # Page 2
    p2 = doc3.new_page()
    p2.insert_text(
        (50, 70),
        "Attention Mechanisms Survey: Optimization & Benchmarks\n\n"
        "Section 3. Optimization Techniques and Learning Dynamics\n"
        "Training large-scale transformer architectures requires specialized optimization regimes:\n"
        "1. AdamW Optimizer: Decoupled weight decay regularization to stabilize gradient updates.\n"
        "2. Warmup Schedules: Linear warmup for the initial 2,000 steps followed by cosine annealing.\n"
        "3. Precision: Mixed precision training (bfloat16 and FP8) significantly decreases memory footprints and increases throughput.\n\n"
        "Section 4. Empirical Evaluation Benchmarks\n"
        "Standardized language evaluation relies on MMLU (Massive Multitask Language Understanding),\n"
        "GSM8K for grade-school mathematical reasoning, and HumanEval for code generation capabilities.\n"
        "Recent scaling laws indicate compute optimal frontier follows Chinchilla scaling (Hoffmann et al., 2022).\n",
        fontsize=11,
    )
    doc3.save(str(out_dir / "deep_learning_survey.pdf"))
    doc3.close()
    print("Created deep_learning_survey.pdf")


if __name__ == "__main__":
    create_sample_pdfs()
